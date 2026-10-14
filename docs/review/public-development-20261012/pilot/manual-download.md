# 原文件下载伴行 Prompt

操作标识：DEV-RAW-PILOT-20261012；项目：graphrag-paper-001；阶段：M2_OPEN。

浏览器控制工具启动失败，原PDF截图也失败。此卡仅补齐已用于开发的两来源，不涉及未来留出。可在新对话粘贴以下Prompt，或直接完成第一步后回到原对话：

> 请帮我完成 DEV-RAW-PILOT-20261012，项目 graphrag-paper-001，阶段 M2_OPEN。每次只指导一步。第一步：用普通浏览器打开 https://nvlpubs.nist.gov/nistpubs/ir/2015/NIST.IR.8091.pdf ，下载原PDF，保存到 D:\graghRAG-agent\docs\review\public-development-20261012\pilot\raw\NIST.IR.8091.pdf。先确认是17页、封面标题 Predicting Robot System Performance by Measuring and Composing Subsystem Attributes，不把网页另存HTML当PDF。未生成实际文件不能报成功。
>
> 完成第一步后再指导第二步：打开 https://linuxcnc.org/docs/2.9/html/config/ini-homing.html ，将完整网页HTML保存至同目录 ini-homing.html；保留附属资源目录。记录页面显示版本和保存时间；若界面不同请让我发截图，不猜按钮，不要求密码、Cookie、令牌或安装软件。随后保存 https://linuxcnc.org/docs/2.9/html/common/gpld-copyright.html 的完整许可页面。不要改原文、运行代码、读其他候选文档、调用外部API或上传文件到第三方。
>
> 结束返回操作卡：project_id、stage_id、operation_task_id、实际文件绝对路径/字节数、官方URL、保存时间、页面版本、限制与失败项。SHA256可由原任务本地计算，不凭空填写。保持M2开放，不自动批准Gold。

接回时只接受这两个已知开发来源，核文件签名/标题/页数/sha256/版面与解析。收到文件不是自动通过；未来留出清单仍单独制定。
