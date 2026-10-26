# PeerWow

Let your agents work together.

[English README](README.md)

PeerWow 是一个让不同人的 Agent 协作完成任务的 Skill。它帮助双方介绍身份、讨论任务、确认各自主人的权限，再多轮交流进展并共同验收。

第一版使用各自已有的邮箱 connector。双方保留自己的 Agent 会话，无需共享代码仓库或搭建新的通讯服务器。Skill 指令、参考文档和界面提示统一使用英文；本文提供中文安装与使用说明。

## 能做什么

- 发起方、接收方和其他参与者使用同一个 Skill。
- 区分人的邮箱地址和每个 Agent 的身份。
- 保存通讯录及双向授信：禁止协作、仅讨论、限定范围协作。
- 允许双方先多轮澄清任务，再由各自主人的授权进入执行。
- 记录任务版本、权限、消息领取、待发预约和停止条件。
- 分开保存本方真实授权与对方报告的授权。

接收方 Agent 听从自己的主人。另一方的邮件不能授予本方执行权限。

## 使用条件

Agent 需要能够读取 Skill 指令，并拥有已授权的邮箱搜索、读取、发送和回复工具。本地状态脚本需要 Python 3.9 或更新版本。附件支持取决于 connector；Agent 会检查实际能力，并在平台提供入口时引导用户连接账号。

邮箱工具负责收发和凭据。`scripts/state.py` 只管理本地记录，不发邮件、不执行附件，也不让 Agent 常驻运行。任务内持续等待取决于宿主平台。复制文件不会调用 Skill；使用下面“安装并开始配置”的完整指令，让 Agent 在当前会话接着引导。对外联系仍需本人明确对象并同意。

## 安装

推荐把仓库链接和这段完整指令一起交给 Agent：

> 从 https://github.com/yx9966/peerwow 安装 PeerWow，并在当前会话立即开始首次配置。读取已安装的 SKILL.md 并执行，不要停在“安装完成”。先检查邮箱能力和已连接账号，缺少连接时引导我使用平台的连接入口，然后与我确认你代表谁、你的 Agent 身份。如果我没有提供联系人，询问我要联系谁、对方邮箱是什么。我同意联系后，继续完成握手并保存已验证的联系人。如果我是来接收邀请的，就回复那封邀请的握手。任务范围明确且获得授权后才能开始执行。

Agent 应先完成检查，再询问缺少的身份、联系人和权限信息。你不用手写一大段技术授权说明；已经明确要求联系某人时，不应重复询问同一次讨论的许可。

已经安装的，可以直接说：

> 从 https://github.com/yx9966/peerwow 更新 PeerWow，保留本地身份、通讯录、任务和已有调度器 ID。在当前会话读取新版 SKILL.md，从实际进度继续。补齐缺少的配置，不重复创建身份、握手或定时任务。对于已经授权的任务，处理待收邮件和待回复事项，核对原线程及固定标题，继续有期限的任务循环。只有确实缺少权限或宿主能力时再问我。

Claude Code 可以输入 `/peerwow`，Codex 可以输入 `$peerwow`。首次直接调用会进入配置。如果当前列表里找不到 Skill，可以让 Agent 直接读取安装位置的 `SKILL.md`。Skill 在调用或匹配任务时加载，PeerWow 没有跨平台的安装后自动执行钩子。参见 [Claude Code](https://code.claude.com/docs/en/skills) 和 [Codex](https://learn.chatgpt.com/docs/build-skills) 官方文档。

### 手动安装文件

将公开仓库克隆到新目录：

```sh
git clone https://github.com/yx9966/peerwow.git
```

要立即试用，可以让 Agent 读取克隆目录中的 `SKILL.md` 并立即开始首次配置，不必等待平台自动发现 Skill。

如果希望安装为个人 Skill，在下面选择一个目标路径，再运行复制命令。目标目录已存在时会停止，以免覆盖已有安装。

```sh
# Codex:
skill_target="${CODEX_HOME:-$HOME/.codex}/skills/peerwow"

# Claude Code: replace the assignment above with this one.
# skill_target="$HOME/.claude/skills/peerwow"

mkdir -p "$(dirname "$skill_target")"
if mkdir "$skill_target"; then
  cp peerwow/SKILL.md "$skill_target/"
  cp -R peerwow/agents peerwow/references peerwow/scripts "$skill_target/"
else
  echo "Target already exists or cannot be created; inspect it before updating."
fi
```

请在克隆目录的上一级执行这些命令。如果当前会话没有刷新 Skill 列表，可以直接让 Agent 读取已安装的 `SKILL.md`，继续使用原会话。

复制后请使用上面的配置指令。Shell 命令只安装文件，不会让 Agent 开始引导。更新前先检查已有安装及本地修改，再替换为指定版本的 Skill 文件；保留 `~/.local/share/peerwow` 中的私有状态，不重置身份、联系人或任务。

其他 Agent 可以通过自身平台的 Skill 机制加载同样的文件。PeerWow 不会为缺少邮箱工具的平台自动增加邮箱能力。

Claude Code 个人安装路径依据其[官方 Skill 文档](https://code.claude.com/docs/en/skills)。上述本地命令不会把 Skill 安装到 Claude Cowork 或云端会话。

## 开始任务

可以向发起方 Agent 提出：

> 使用 PeerWow，与 colleague@example.test 的同事讨论一个解析器验证任务。确认双方身份和能力，先商定任务与验收标准，再执行。本次试用只使用合成数据。

把示例邮箱替换为真实且已获准联系的接收者。接收方本人可以在自己的 Agent 会话中说：

> 使用 PeerWow，读取我指定同事发来的任务邀请。与对方 Agent 讨论清楚任务，说明需要我授权哪些操作，缺少权限时先向我确认再执行。

只联系本方主人授权的对象。安装、收到邀请或远端声称已经获得同意，都不等于本方执行授权。

## 任务内持续通讯

本人授权持续通讯后，Agent 会使用可用的宿主能力注册有期限的任务循环，等待对方时每 5 分钟检查一次；已有本地工作和待回复邮件立即处理。状态脚本返回查信、工作、等待或停止等动作，防止同一状态库中的循环重叠，并要求收到的消息在完成前记录已发送的回复，或明确说明为何无需回复。到期、撤权或发信额度耗尽时停止。

宿主调度器负责触发 Agent；单独的 Python 定时器不能直接取得现有邮箱 connector 或唤起 Agent。支持的 Claude Code 安装有会话内调度能力，Agent 必须检查当前工具是否可用。其他平台可能提供当前回合结束后仍触发的聊天自动化，这种行为需要本人授权。双方各管自己的权限；缺少能力时必须报告阻塞，不能声称已经实现无人值守。

任务回信必须使用真实回复标识。脚本核对发送后返回的线程 ID，发现分叉时停止推进，并保留已发送记录，避免重复发信。详见英文版[循环接入与恢复](references/task-loop.md)。

新任务标题固定为 `[PeerWow][任务号] 本人A/AgentA <-> 本人B/AgentB | 具体任务名称`。回信保留标题及双方顺序，进展和版本写正文。已经建立的线程保留原标题，避免更新时拆散正在进行的对话。

## 本地记录与权限

状态保存在 Skill 安装目录之外：`~/.local/share/peerwow/state.json`。可通过 `PEERWOW_HOME` 或脚本的 `--root` 参数指定其他位置。脚本使用时才创建状态文件，仓库不包含真实通讯录。

每个本方 Agent 与对方 Agent 的关系，都分别保存本方授信和对方报告的反向授信。记录包含允许事项、禁止事项、版本、可选有效期和来源依据。已有联系人不自动获得新任务执行许可；授信变化会使旧的执行确认失效。

消息与授信约定见[协议说明](references/protocol.md)，脚本命令见[接入与状态说明](references/setup-state.md)。这两份 Agent 参考文档均为英文。不要公开状态文件、邮箱凭据或私有任务邮件。

## 开发与验证

在仓库根目录运行离线测试：

```sh
python3 -m unittest discover -s tests -v
```

39 项测试使用合成身份和临时状态，不访问邮箱、不发信，也不依赖本机已安装的 Skill。详见英文版[验证范围](tests/VALIDATION.md)。

此前的一轮人工发起邮件协作为本设计提供了依据。包含通讯录和双向授信的完整 Skill 尚未完成真实双端验收。本地测试不能证明所有 Agent 都会遵守指令。

脚本检查等级、期限、版本及记账状态，无法核实人类授权真实性、理解自然语言权限范围、为单个 Agent 提供密码学身份认证，或阻止工具绕过它。没有离线唤醒服务，也不能保证远端 Agent 立即收到撤回通知。
