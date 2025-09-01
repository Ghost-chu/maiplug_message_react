# maiplug_message_react
麦麦插件，让麦麦学会怎么给消息贴表情吧

<img width="832" height="427" alt="PixPin_2025-09-01_22-10-20" src="https://github.com/user-attachments/assets/e0a68cd3-718b-464b-b9e8-e7c1926421c3" />

## 配置

1. 首选确认麦麦的 `model_config.toml` 中的 `model_task_config.tool_use` 是否已配置，如果没配置将无法使用。需要模型有一定智商和情商，如果出现问题，建议使用火山引擎的 `doubao-seed-1-6-25061` 模型。
2. 下载插件，然后丢进 `plugins` 文件夹里，重新启动以生成 `config.toml` 配置文件
3. 打开 Napcat WebUI 控制台，转到*网络配置*菜单，添加一个 HTTP 服务器，Host 填写 `0.0.0.0` Port 可以自行决断，其他选项保持默认。
4. 编辑刚刚生成的 `config.toml` 配置文件，配置 *Napcat服务地址*、*Napcat 服务端口* 和 *Napcat服务认证Token*   
  4.1 对于跟随麦麦官方 Docker 教程部署的用户，Napcat 服务地址可直接使用 `napcat`
5. 重新启动麦麦，在群里艾特一下让麦麦给你贴个表情，能贴了就说明装好了
