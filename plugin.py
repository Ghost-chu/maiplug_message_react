import json
from typing import List, Tuple, Type

from src.chat.knowledge.utils.json_fix import fix_broken_generated_json
from src.chat.utils.utils import translate_timestamp_to_human_readable
from src.common.data_models.message_data_model import MessageAndActionModel
from src.common.logger import get_logger
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    BaseAction,
    ComponentInfo,
    ActionActivationType,
    ConfigField
)
from src.plugin_system.apis import message_api, llm_api
from src.plugin_system.apis.database_api import store_action_info

logger = get_logger("msg_react")
available_react_emojis = {76: "点赞", 307: "喵喵", 285: "摸鱼",
                          66: "爱心", 147: "棒棒糖", 424: "狂按按钮",
                          49: "抱抱", 38: "木槌敲头", 277: "狗头",
                          265: "辣眼睛", 390: "头秃", 63: "玫瑰",
                          212: "托腮", 5: "大哭", 9: "委屈",
                          350: "贴贴", 175: "卖萌", 344: "大怨种",
                          187: "鬼魂", 144: "礼花", 146: "爆筋",
                          311: "打call", 59: "便便", 46: "猪头",
                          37: "骷髅头", 317: "菜狗", 124: "OK"}


class MessageReactAction(BaseAction):


    """处理消息反应的 Action"""
    action_name = "msg_react"
    action_description = "向指定群聊消息添加反应表情，表情会显示在对应消息的下面"
    parallel_action = True
    activation_type = ActionActivationType.ALWAYS

    action_require = [
        "需要或想要对消息添加反应表情时",
        "表达情绪时可以选择使用",
        "当你想要和某人友好互动时可选择调用",
        "当你想要提醒某人时可选择调用",
        "提示：贴反应表情的Action不视为回复消息。无论什么时候，若与reply同时出现在选择中，应优先选择reply的action",
    ]

    associated_types = ["text", "emoji", "image", "reply", "voice"]

    llm_judge_prompt = """
    判定是否需要使用反应动作的条件：
    1. 用户明确要求为其消息添加反应表情
    2. 你需要或者想要对消息添加反应表情以表达情绪
    3. 你想要和某人友好互动，但又不想发送消息破坏聊天节奏
    3. 不要发送太多反应表情，如果你已经发送过多个反应表情则回答"否"

    请回答"是"或"否"。
    """

    async def execute(self) -> Tuple[bool, str]:
        """执行问候动作 - 这是核心功能"""
        # 发送问候消息
        if not self.is_group:
            return False, "消息反应仅支持群聊"
        chat_id = self.action_message.chat_id
        available_emojis_prompt = ", ".join(
            [f"{emoji_id}:{emoji_name}" for emoji_id, emoji_name in available_react_emojis.items()])
        recent_messages = message_api.get_recent_messages(chat_id=self.chat_id, limit=15)
        messages_text = ""
        if recent_messages:
            # 使用message_api构建可读的消息字符串
            # <ID>, <时间(相对)>, <用户>: <内容>
            list_message = []
            for msg in recent_messages:
                maam = MessageAndActionModel.from_DatabaseMessages(msg)
                user_name = maam.user_nickname
                content = maam.processed_plain_text.replace("\n", " ").replace("\r", " ")
                msg_id = msg.message_id
                timestamp = translate_timestamp_to_human_readable(maam.time, mode="relative")
                list_message.append(f"{msg_id},{timestamp},{user_name}:{content}")
            messages_text = "\n".join(list_message)

        logger.info(f"最近消息: {messages_text}")
        # 4. 构建prompt让LLM选择情感
        prompt = f"""
你是一个正在进行聊天的网友，你需要根据一个和最近的聊天记录，从一个反应表情列表中选择最匹配的一个反应表情的数字ID。
这是最近的聊天记录列表，消息的格式为："<id>,<time>,<user>:<content>" 一行一个：
{messages_text}
以下是是可用的反应表情，ID 在前，名称在后，不同反应表情间用","分割：
{available_emojis_prompt}
请严格按下列的 JSON 格式返回最匹配的那个反应表情 ID 和消息 ID，不要进行任何解释或添加其他多余的文字：
{{
  "message_id": "要贴反应表情的消息ID",
  "emoji_id": "选择的对应反应表情ID"
}}
"""
        logger.info(f"生成的LLM Prompt: {prompt}")

        # 5. 调用LLM
        models = llm_api.get_available_models()
        chat_model_config = models.get("tool_use")  # 使用字典访问方式
        if not chat_model_config:
            logger.error(f"未找到'tool_use'模型配置，无法调用LLM")
            return False, "未找到'tool_use'模型配置"

        success, chosen_react_emoji_json_str, _, _ = await llm_api.generate_with_model(
            prompt, model_config=chat_model_config, request_type="text"
        )
        logger.debug(f"LLM返回: {chosen_react_emoji_json_str}")
        fixedResp = fix_broken_generated_json(chosen_react_emoji_json_str)
        logger.debug(f"LLM修复: {fixedResp}")
        json_resp = json.loads(fixedResp)
        if not success:
            logger.error(f"LLM调用失败: {chosen_react_emoji_json_str}")
            return False, f"LLM调用失败: {chosen_react_emoji_json_str}"
        selected_message_id = json_resp["message_id"]
        chosen_react_emoji_id = json_resp["emoji_id"].strip().replace('"', "").replace("'", "")
        chosen_react_emoji_name = available_react_emojis.get(int(chosen_react_emoji_id))
        logger.debug(f"LLM响应解析: {selected_message_id}, {chosen_react_emoji_id}: {chosen_react_emoji_name}")
        await self.send_msg_react(chat_id, selected_message_id, chosen_react_emoji_id,
                                  self.get_config("napcat.host", "napcat"),
                                  self.get_config("napcat.port", 9999),
                                  self.get_config("napcat.token", None))
        await store_action_info(self.chat_stream, True,
                                f"[反应表情：贴在了消息ID={selected_message_id}上，表情是={chosen_react_emoji_name}]",
                                True,
                                self.thinking_id,
                                self.action_data,
                                self.action_name)
        return success == True, f"反应表情：贴在了消息ID={selected_message_id}上，表情是={chosen_react_emoji_name}"

    async def send_msg_react(self, chat_id, message_id, chosen_react_emoji, napcat_host, napcat_port, napcat_token) -> Tuple[bool, str]:
        import http.client
        conn = http.client.HTTPConnection(napcat_host, napcat_port)
        payload = {"message_id": message_id, "emoji_id": chosen_react_emoji, "set": True}
        payload = json.dumps(payload)
        headers = {"Content-Type": "application/json"}
        if napcat_token:
            headers["Authorization"] = napcat_token
        logger.debug(f"发送消息反应: chat_id={chat_id}, message_id={message_id}, emoji_id={chosen_react_emoji}")
        try:
            conn.request("POST", "/set_msg_emoji_like", payload, headers)
            res = conn.getresponse()
            data = res.read()
            result = data.decode("utf-8")
            logger.debug(f"贴表情响应: {result}")
            try:
                data_json = json.loads(result)
                return data_json.get("status") == "ok", data_json.get("message", result)
            except Exception as e:
                error_info = {
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
                return False, f"贴表情失败 {error_info}"
        except Exception as e:
            error_info = {
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
            logger.error(f"贴表情异常: {error_info}")
            return False, f"贴表情失败 {error_info}"


# ===== 插件注册 =====


@register_plugin
class MessageReactPlugin(BasePlugin):
    """Hello World插件 - 你的第一个MaiCore插件"""

    # 插件基本信息
    plugin_name: str = "maiplug_message_react"  # 内部标识符
    enable_plugin: bool = True
    dependencies: List[str] = []  # 插件依赖列表
    python_dependencies: List[str] = []  # Python包依赖列表
    config_file_name: str = "config.toml"  # 配置文件名

    # 配置节描述
    config_section_descriptions = {"plugin": "插件基本信息"}

    # 配置Schema定义
    config_schema: dict = {
        "plugin": {
            "name": ConfigField(type=str, default="maiplug_message_react", description="插件名称"),
            "version": ConfigField(type=str, default="1.0.0", description="插件版本"),
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
        },
        "napcat": {
            "host": ConfigField(type=str, default="napcat", description="Napcat服务地址"),
            "port": ConfigField(type=int, default=9999, description="Napcat服务端口"),
            "token": ConfigField(type=str, default="", description="Napcat服务认证Token"),
        }
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        return [ (MessageReactAction.get_action_info(), MessageReactAction)]
