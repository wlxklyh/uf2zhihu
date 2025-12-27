# 预算有限的 Horde 部署：小团队的成本效益型基础设施方案

> 基于 Unreal Fest Bali 2025 技术演讲整理  
> 演讲者：Ash (S1T2 实时开发负责人)  
> 视频时长：43分47秒

---

## 摘要

本文详细介绍了如何在预算有限的情况下，为小型开发团队部署 Epic Games 的 Horde 持续集成平台。文章涵盖了从基础设施规划、云服务选择、Perforce 配置、身份认证集成到通知系统定制的完整流程，并分享了多个降低成本的实用技巧。

**关键要点：**
- Horde 最小化部署方案及成本优化策略
- 混合云架构设计：关键服务上云，构建代理本地化
- Perforce 流配置与代理服务器设置
- 第三方服务集成（Auth0、Discord）
- Horde 插件开发实践

---

## 一、背景介绍

### 1.1 关于演讲者与团队

![演讲者介绍](screenshots/007_plus0.0s.png)

我是 Ash，目前在 S1T2 担任实时开发负责人。我的主要工作是领导基于 Unreal Engine 的沉浸式体验项目开发，同时也负责维护和开发这些项目的 DevOps 流水线。

**S1T2 团队特点：**
- 主要为博物馆和美术馆创建沉浸式交互体验
- 团队规模较小，但会根据项目需求扩展承包商或合作伙伴
- 采用混合办公模式（办公室、远程、跨国现场）
- 重视快速迭代，项目周期短且需求变化频繁

![S1T2 工作场景](screenshots/023_plus0.0s.png)

这种工作模式决定了我们需要一个稳定可靠的远程访问基础设施。实际上，我曾经因为在迪拜的项目被困在那里五个月，远程访问能力在那段时间至关重要。

### 1.2 目标受众

本文适合以下团队：
- 对 Horde 感兴趣但不确定是否适合的小团队
- 尚未建立持续集成系统的团队
- 希望优化现有 CI/CD 成本的团队

如果您对 Horde 或类似工具有一定了解会更好，但即使是新手也能从中获益。

---

## 二、为什么选择 Horde？

### 2.1 Horde 是什么

![Horde 简介](screenshots/032_plus0.0s.png)

Horde 是 Epic Games 的定制持续集成平台。称其为"持续集成平台"可能过于简化——它的独特之处在于对 Unreal 工具、项目和工作流程的原生支持。

**核心特性：**
- 原生支持 BuildGraph
- 与 Unreal GameSync 等 Epic 工具深度集成
- 为企业级规模设计（Epic 内部使用规模参考）

### 2.2 选择 Horde 的理由

![Horde 优势](screenshots/039_plus0.0s.png)

**开箱即用体验无与伦比**

对于 Unreal Engine 项目，Horde 的开箱即用体验是无可比拟的，这主要归功于：
- 原生集成减少配置工作
- 流程简化，学习曲线平缓
- 一体化解决方案，减少工具间的"胶水代码"

**深度融入 Unreal 生态**

选择 Horde 意味着融入 Epic 的工具生态系统，这降低了引入更多 Epic 工具的摩擦成本。

**为规模而生**

如果您是全球规模的团队，Horde 的可扩展性设计能够满足大型团队的需求。

### 2.3 不选择 Horde 的理由

![Horde 限制](screenshots/051_plus0.0s.png)

**工作流程固化**

Horde 在工作流程和集成方面有自己的主见。如果这些不适合您的团队，可能不是最佳选择。

**Perforce 依赖**

Horde 深度集成 Perforce。虽然可以迁移到 Perforce 或想办法集成其他版本控制系统，但这可能需要大量工作。

**项目类型限制**

如果您的工作室同时运行 Unreal 和非 Unreal 项目，Horde 对非 Unreal 项目的支持较弱。

**现有方案的惯性**

如果您已经有一套运行良好的系统，很难说服团队迁移到新平台。

---

## 三、Horde 部署需求分析

### 3.1 Epic 的 Horde 部署规模

![Epic 部署规模](screenshots/067_plus0.0s.png)

让我们先看看 Epic 的部署规模，这有助于理解 Horde 的设计目标：

- Amazon 负载均衡器
- 12 个 Linux 容器运行 Horde 服务和控制面板
- DocumentDB 和 ElastiCache 数据库
- 数百个 EC2 实例运行 Horde Agent
- 额外 100+ 台本地物理机

这个规模显然超出了小团队的需求。

### 3.2 最小化部署方案

![最小部署](screenshots/073_plus0.0s.png)

**核心组件（必需）：**

1. **Horde 服务器** - 核心服务
2. **MongoDB** - 主数据库
3. **Redis** - 缓存数据库（或兼容方案）
4. **Web 服务器** - 提供控制面板访问

5. **存储方案** - 存储构建产物和日志
   - 可以使用本地文件系统
   - 也可以使用云存储（如 S3）

6. **至少一个 Agent** - 执行实际构建任务

7. **Perforce 服务器** - 存储项目、引擎和 Horde 配置

### 3.3 可选的外部服务

![外部服务](screenshots/081_plus0.0s.png)

**身份认证提供商**
- 提供登录流程和用户管理
- 支持 OIDC 标准的服务

**通知服务**
- Horde 原生支持 Slack
- 可以通过插件支持其他平台（Discord、Teams 等）

**问题追踪系统**
- 可集成 Jira（本文不详细讨论）

---

## 四、基础设施部署策略

### 4.1 部署位置选择

![部署选项](screenshots/088_plus0.0s.png)

我们需要决定：将所有内容部署在云端、本地，还是采用混合方案？

**本地部署**
- ✅ 长期成本较低（一次性硬件投资）
- ❌ 扩展性差（无法快速增加资源）
- ❌ 稳定性较低（易受停电、断网、硬件故障影响）

**云端部署**
- ✅ 高可用性和稳定性
- ✅ 按需扩展能力
- ❌ 长期成本较高

**混合部署（推荐）**
- ✅ 兼顾两者优势
- ✅ 提供灵活的迁移路径
- 🔄 成本介于两者之间

### 4.2 混合架构设计

![混合架构](screenshots/103_plus0.0s.png)

**我们的方案：**

**云端部署（关键基础设施）**
- Horde 服务器
- 数据库（MongoDB、Redis）
- Perforce 服务器
- 存储服务（S3）

这些组件的中断影响最大，因此部署在云端以获得更高的稳定性。

**本地部署（构建资源）**
- Build Agent
- Perforce Proxy
- Unreal GameSync

![本地部署](screenshots/106_plus0.0s.png)

将 Agent 放在本地可以：
- 节省高性能云服务器的持续费用
- 复用现有硬件资源
- 降低长期运营成本

---

## 五、Horde 服务器部署

### 5.1 数据库选择

![数据库选项](screenshots/112_plus0.0s.png)

**方案一：AWS 托管数据库**
- DocumentDB（MongoDB 兼容）
- ElastiCache（Redis 兼容）
- ✅ 高可用性和自动备份
- ✅ 开箱即用
- ❌ 成本较高

**方案二：自建数据库（EC2）**
- 直接在 EC2 上部署 MongoDB 和 Redis
- ✅ 成本较低
- ❌ 需要手动配置备份和扩展
- 🔄 仍保留未来扩展的可能性

**方案三：单机 Docker 方案（我们的选择）**

![Docker 方案](screenshots/118_plus0.0s.png)

- 在单个 EC2 实例上使用 Docker 运行所有服务
- ✅ 成本最低（只需一台服务器）
- ❌ 扩展性最差（未来需要迁移）
- ✅ 适合小团队初期需求

**决策依据：**
对于小团队，单机方案的成本优势明显，而横向扩展能力并非当前必需。

### 5.2 控制面板托管

![控制面板](screenshots/123_plus0.0s.png)

控制面板是一个静态网站，有多种托管选择：
- 通用 Web 服务器
- AWS 静态网站服务
- **Horde 服务器自身（我们的选择）**

**选择理由：**
- 控制面板负载很轻，对性能影响微乎其微
- 避免增加部署复杂度
- 唯一的权衡：更新控制面板需要重新部署整个 Horde 镜像

### 5.3 存储后端选择

![存储选择](screenshots/127_plus0.0s.png)

Horde 需要存储构建产物和日志文件。

**EBS 卷（本地存储）**
- ✅ I/O 性能更好（在无瓶颈情况下）
- ❌ 需要预先分配容量
- ❌ 每 GB 成本较高

**S3（云存储）**

![S3 优势](screenshots/135_plus0.0s.png)

- ✅ 按需付费，无存储上限
- ✅ 成本较低
- ✅ **支持预签名 URL**

**预签名 URL 的重要性：**

使用预签名 URL，客户端（Agent、用户）可以直接从 S3 上传/下载数据，绕过 Horde 服务器。这极大减轻了服务器负载，让我们能够使用更小规格的实例。

**最终选择：S3**

---

## 六、构建代理配置

### 6.1 硬件选择建议

![硬件需求](screenshots/140_plus0.0s.png)

**核心组件：**

**CPU**
- 需要多核心处理器
- 核心越多，并行能力越强

**存储**
- 强烈推荐 SSD
- Agent 需要频繁读写文件，避免 I/O 成为瓶颈

**GPU**
- 可选项
- 取决于是否运行自动化测试及测试类型

**内存**

![内存需求](screenshots/145_plus0.0s.png)

内存配置需要特别注意。如果编译过 Unreal Engine 项目，您可能见过这样的消息：

```
限制为每个逻辑核心 1 个进程（共 20 个）
每个进程需要 1.5GB 内存
当前可用内存：25GB
因此限制为 16 个进程（20 个中）
```

这意味着内存不足以"喂饱"所有 CPU 核心。

**推荐配置：**
- **保守方案**：每线程 2GB 内存（留有充足缓冲）
- **最小方案**：每线程 1.5GB + 缓冲

### 6.2 内存限制器配置

![内存限制器](screenshots/152_plus0.0s.png)

Unreal 的内存限制器是人为的，可以禁用：

```ini
[BuildConfiguration]
bIgnoreMemoryPerActionLimit=true
```

虽然在内存不足时禁用限制器可能有帮助，但**最好确保内存本身足够**。

我们在 Build Agent 上禁用了这个限制器，以应对内存使用峰值，确保始终使用最大并行度。

### 6.3 BuildGraph 优化

![BuildGraph 优化](screenshots/156_plus0.0s.png)

还有一个 `bAllCores` 布尔值需要注意。这个值在某些 BuildGraph 任务在 Horde Agent 上运行时会被设置为 true，但并非所有任务都会。

建议显式设置：

```xml
<Property Name="bAllCores" Value="true"/>
```

---

## 七、Perforce 服务器配置

### 7.1 基本要求

![Perforce 要求](screenshots/159_plus0.0s.png)

使用 Horde 有两个关键的 Perforce 要求：

**1. 引擎源码必须在 Perforce 上**

![引擎源码](screenshots/160_plus0.0s.png)

即使您不打算修改引擎，也需要考虑如何组织 Perforce 流来容纳引擎源码。

**2. 项目必须是"原生"结构**

![原生结构](screenshots/162_plus0.0s.png)

项目必须满足以下条件之一：
- 项目文件夹相对于引擎目录
- 如果在子目录中，该子目录需在 `UprojectDirs` 文件中列出

### 7.2 流（Stream）结构设计

![流结构](screenshots/163_plus0.0s.png)

**最小配置（两个流）：**

1. **入口流**：包含纯净的 Unreal Engine，无任何修改
2. **开发流**：实际进行开发的地方

**推荐配置（三个流）：**

![三层流](screenshots/166_plus0.0s.png)

1. **入口流**（UE-Engine-Entry）：纯净引擎
2. **缓冲流**（UE-Engine-Merge）：合并引擎更新和自定义修改
3. **开发流**（UE-Engine-Main）：日常开发

**缓冲流的价值：**
提供一个独立的位置来处理上游引擎更新与本地修改的合并冲突。

### 7.3 实际案例：S1T2 的流结构

![S1T2 流结构](screenshots/169_plus0.0s.png)

我们的设置略有不同：
- **UE-Main**：入口流
- **UE-Dev**：主要作为缓冲，但也进行部分开发
- **项目专属流**：从 UE-Dev 分支出来，每个项目一个流

![发布流](screenshots/171_plus0.0s.png)

我们还有一些**发布流**，它们是我们导入引擎时的快照，主要用于编译插件。

### 7.4 使用 Stream Components

![Stream Components](screenshots/175_plus0.0s.png)

**什么是 Stream Components？**

Stream Components 允许我们创建一个独立的项目流，然后将该流的内容映射到任何引擎工作区中。

同步引擎流时，项目会自动出现在子目录中。

**优势：**

![Components 优势](screenshots/177_plus0.0s.png)

- **解耦**：引擎和项目流可以独立合并和分支
- **灵活性**：可以混合搭配不同版本的引擎和项目
- **可逆性**：可以追溯应用或撤销，无需在流之间移动文件

---

## 八、Perforce Proxy 优化

### 8.1 为什么需要 Proxy

![Perforce Proxy](screenshots/180_plus0.0s.png)

Perforce Proxy 本质上是客户端和服务器之间的缓存层。

**工作原理：**
- 如果 Proxy 已有客户端请求的文件，直接返回
- 无需从服务器重新下载
- **降低服务器负载**
- **提高同步速度**

### 8.2 理想的拓扑结构

![Proxy 拓扑](screenshots/182_plus0.0s.png)

我们希望实现：
- **本地 Agent** → Perforce Proxy
- **Horde 服务器** → 直连 Perforce 服务器

### 8.3 实现方法：主机名解析

![主机名解析](screenshots/183_plus0.0s.png)

**核心思路：**创建一个主机名，在不同机器上解析到不同 IP。

**在 Agent 上（本地机器）：**

编辑 hosts 文件：

```
192.168.1.100  perforce.internal
```

这会让 `perforce.internal` 解析到 Proxy 的 IP（本地网络）。

**在 Horde 服务器上（Docker 容器）：**

![Docker 配置](screenshots/185_plus0.0s.png)

编辑 `docker-compose.yml`：

```yaml
extra_hosts:
  - "perforce.internal:203.0.113.10"
```

这让同一主机名解析到 Perforce 服务器的公网 IP。

**Horde 配置：**

在 Horde 配置中使用统一的主机名 `perforce.internal`，这样 Agent 和服务器都能正确连接。

### 8.4 运行 Perforce Proxy

![运行 Proxy](screenshots/187_plus0.0s.png)

运行 Proxy 非常简单：

```bash
p4p -p <proxy_ip>:<port> -t <server_ip>:<port> -r <cache_dir>
```

参数说明：
- `-p`：Proxy 绑定的 IP 和端口
- `-t`：Perforce 服务器的 IP 和端口
- `-r`：缓存文件存储目录

---

## 九、Unreal GameSync 集成

### 9.1 什么是 Unreal GameSync

![UGS 介绍](screenshots/191_plus0.0s.png)

Unreal GameSync（UGS）是一个桌面工具，主要功能是简化从 Perforce 同步引擎和项目的流程。

**核心功能：**
- 一键同步、构建和运行项目
- 同步过滤器
- 下载预编译二进制文件（PCB）

**前提条件：**必须使用原生文件夹结构。

### 9.2 为什么使用 UGS

![UGS 价值](screenshots/196_plus0.0s.png)

**自动化工作流**
- 一键完成：同步 → 编译 → 运行
- 减少人为错误

**仪表板功能**

![UGS 仪表板](screenshots/197_plus0.0s.png)

- 快速查看项目健康状况和变更列表
- 启动其他工具（Unreal Insights、Swarm 等）

**预编译二进制文件**

![PCB](screenshots/198_plus0.0s.png)

最大的优势：开发者可以同步并运行项目，**无需安装 Visual Studio**。

### 9.3 UGS 部署需求

![UGS 部署](screenshots/200_plus0.0s.png)

除了 Perforce 服务器，UGS 还需要三个额外组件：

1. **元数据服务器**
   - 提供 Perforce 之外的额外信息
   - 如注释、构建系统生成的标签等

2. **UGS 客户端下载位置**
   - 用户下载安装程序的地方
   - 支持自动更新功能

3. **预编译二进制文件存储**
   - 存储和分发 PCB

### 9.4 传统方案 vs Horde 方案

**传统方案：**

![传统方案](screenshots/204_plus0.0s.png)

- 独立的元数据服务器
- 在 Perforce 上创建两个额外的流：
  - UGS 二进制文件流
  - 编辑器 PCB 流
- 需要手动通过 HTTP API 与元数据服务器通信（编写胶水代码）

**Horde 一体化方案：**

![Horde 方案](screenshots/207_plus0.0s.png)

✅ **Horde 现在充当元数据服务器**  
✅ **Horde 存储二进制文件**  
✅ **无需额外的 Perforce 流**  
✅ **深度集成，无需胶水代码**

这正是 Horde 深度集成的价值所在。

### 9.5 配置步骤

**步骤 1：配置 UGS**

![UGS 配置](screenshots/211_plus0.0s.png)

非常简单，只需在项目的 `.ini` 文件中添加：

```ini
[UGS]
MetadataServer=https://your-horde-server.com
```

**步骤 2：上传 PCB**

![BuildGraph 配置](screenshots/212_plus0.0s.png)

在 BuildGraph 脚本中，找到生成二进制文件的节点。

添加 Artifact 元素：

```xml
<Node Name="CompileEditor">
    <!-- 现有的编译步骤 -->
    
    <Artifact Type="Unreal-Editor" Keys="Win64" BaseDir="..." />
</Node>
```

![Artifact 配置](screenshots/214_plus0.0s.png)

设置正确的 `Type` 和 `Keys`，UGS 就能自动找到并下载这些文件。

---

## 十、身份认证集成

### 10.1 OIDC 简介

![OIDC 介绍](screenshots/222_plus0.0s.png)

OIDC（OpenID Connect）是一个标准协议，提供两个核心功能：

1. **登录流程**
   - 允许用户使用外部账户登录（如 Google、GitHub）

2. **用户身份**
   - 登录后接收用户信息（姓名、邮箱等）

### 10.2 Horde 的两种登录流程

**流程 1：控制面板登录**

![控制面板登录](screenshots/227_plus0.0s.png)

1. 访问 Horde 服务器
2. 自动重定向到身份提供商登录页
3. 输入凭据并登录
4. 重定向回 Horde 控制面板（已登录状态）

**流程 2：桌面工具登录（如 UGS）**

![UGS 登录](screenshots/231_plus0.0s.png)

1. UGS 启动本地 HTTP 服务器
2. 打开浏览器到身份提供商登录页
3. 登录
4. 重定向到本地 HTTP 服务器
5. UGS 接收并存储身份信息

### 10.3 用户身份和权限

![Claims](screenshots/237_plus0.0s.png)

登录后，Horde 接收一系列描述用户的 **Claims**（声明）：

```json
{
  "email": "user@example.com",
  "name": "John Doe",
  "picture": "https://..."
}
```

![权限配置](screenshots/240_plus0.0s.png)

Horde 可以基于 Claims 分配权限：

```json
{
  "claim": "email",
  "value": "ash@s1t2.com",
  "permissions": ["ExecuteJobs", "ViewDashboard"]
}
```

### 10.4 提供商选择

![提供商选择](screenshots/242_plus0.0s.png)

市面上有多个提供商可选，许多需要付费。

**Horde 内置提供商**
- ✅ 免费
- ✅ 设置简单
- ⚠️ 不建议公网暴露

**Auth0（我们的选择）**

![Auth0](screenshots/246_plus0.0s.png)

- ✅ 免费额度：25,000 用户
- ✅ 功能完整
- ✅ **集成 Google Workspace**（可使用公司 Google 账户）

### 10.5 Auth0 配置详解

**步骤 1：认证方法**

![认证方法](screenshots/255_plus0.0s.png)

Horde 配置文件中的 `AuthMethod` 选项：
- `Anonymous`：无认证
- `Okta`：Okta 提供商
- `OpenIdConnect`：通用 OIDC（Auth0 使用这个）
- `Horde`：内置提供商

```json
{
  "AuthMethod": "OpenIdConnect"
}
```

**步骤 2：OIDC Authority**

![Authority](screenshots/259_plus0.0s.png)

创建 Auth0 租户后，会得到一个 URL：

```
https://your-tenant.auth0.com
```

将其设置为 Authority：

```json
{
  "OidcAuthority": "https://your-tenant.auth0.com"
}
```

**步骤 3：Audience（受众）**

![Audience](screenshots/262_plus0.0s.png)

在 Auth0 中创建 API，设置 Identifier（可以是任何值，通常格式化为 URL）：

```
https://horde-api.example.com
```

将其设置为 Audience：

```json
{
  "OidcAudience": "https://horde-api.example.com"
}
```

**步骤 4：客户端 ID 和密钥**

![Client ID](screenshots/267_plus0.0s.png)

在 Auth0 创建应用（选择"Single Page Web Application"）。

![回调 URL](screenshots/269_plus0.0s.png)

设置允许的回调 URL：

```
https://your-horde.com/account/signin-oidc
http://localhost:PORT/login
```

从应用设置页面复制：

```json
{
  "OidcClientId": "your-client-id",
  "OidcClientSecret": "your-client-secret"
}
```

**步骤 5：服务器 URL**

```json
{
  "ServerUrl": "https://your-horde.com"
}
```

如果不设置，会默认为机器名或容器名。

### 10.6 Auth0 额外配置

**限制访问**

![限制访问](screenshots/280_plus0.0s.png)

1. **禁用 Google 社交连接**
   - 默认启用，意味着任何 Google 账户都能登录
   - 必须禁用！

2. **禁用用户注册**
   - 防止任何人自行创建账户

![禁用注册](screenshots/284_plus0.0s.png)

**设置默认 Audience**

![默认 Audience](screenshots/287_plus0.0s.png)

这个设置非常重要！

UGS 等桌面工具在认证请求中不会提供 `audience` 参数，但 Auth0 需要它。设置默认 Audience 后，Auth0 会自动注入这个参数。

```json
{
  "default_audience": "https://horde-api.example.com"
}
```

**没有这个设置，UGS 登录会失败！**

---

## 十一、通知系统定制

### 11.1 为什么需要自定义方案

![通知需求](screenshots/300_plus0.0s.png)

Horde 有通知系统，可以向外部服务报告事件，避免手动检查控制面板。

**问题：**
- Horde 原生支持 Slack
- Slack 需要付费才能获得完整功能
- 我们使用 Discord

![Discord](screenshots/305_plus0.0s.png)

我们不想为了 Horde 通知而迁移到 Slack 或同时使用两个平台。

### 11.2 Horde 插件系统

![插件接口](screenshots/307_plus0.0s.png)

幸运的是，Horde 提供了多个扩展接口，其中之一是 `INotificationSink`（通知接收器接口）。

![插件优势](screenshots/310_plus0.0s.png)

**插件的优势：**
- 无需直接修改 Horde 代码
- 创建 DLL 供 Horde 加载即可

### 11.3 Discord 集成方案

**方案选择：**

![Webhook](screenshots/313_plus0.0s.png)

1. **Discord Bot**
   - ✅ 功能更强大（创建频道等）
   - ❌ 设置复杂

2. **Webhook（我们的选择）**
   - ✅ 设置简单
   - ✅ 通用性强（其他平台也适用）
   - 只需向 HTTP 端点发送 JSON 数据

### 11.4 实现步骤

**步骤 1：创建插件类**

![插件类](screenshots/327_plus0.0s.png)

```csharp
[PluginConfig]
public class DiscordPlugin : IHordePlugin
{
    public void Configure(IServiceCollection services)
    {
        // 注册服务
    }
}
```

这是 Horde 加载 DLL 时寻找的入口点。

**步骤 2：实现通知接收器**

![通知接收器](screenshots/330_plus0.0s.png)

```csharp
public class DiscordNotificationSink : INotificationSink
{
    public async Task NotifyJobCompleteAsync(/* 参数 */)
    {
        // 实现通知逻辑
    }
}
```

![关键函数](screenshots/332_plus0.0s.png)

关键函数是 `NotifyJobCompleteAsync`，当作业完成时被调用。

**步骤 3：定义 Discord 消息结构**

![消息结构](screenshots/333_plus0.0s.png)

```csharp
public class DiscordMessage
{
    public List<DiscordEmbed> Embeds { get; set; }
}

public class DiscordEmbed
{
    public string Title { get; set; }
    public int Color { get; set; }
    public string Description { get; set; }
}
```

这些类匹配 Discord Webhook API 的 JSON 架构。

**步骤 4：构建和发送消息**

![构建消息](screenshots/337_plus0.0s.png)

```csharp
// 从配置读取 Webhook URL
var webhookUrl = stream.NotificationChannel;

// 准备消息
var message = new DiscordMessage
{
    Embeds = new List<DiscordEmbed>
    {
        new DiscordEmbed
        {
            Title = $"Job {jobName} {outcome}",
            Color = outcome == "Success" ? 0x00FF00 : 0xFF0000,
            Description = $"Change: {changelist}\n{description}"
        }
    }
};

// 序列化为 JSON
var json = JsonSerializer.Serialize(message);

// 发送 HTTP POST 请求
var content = new StringContent(json, Encoding.UTF8, "application/json");
await httpClient.PostAsync(webhookUrl, content);
```

**步骤 5：注册插件**

![注册插件](screenshots/348_plus0.0s.png)

```csharp
public void Configure(IServiceCollection services)
{
    services.AddSingleton<INotificationSink, DiscordNotificationSink>();
}
```

### 11.5 扩展可能性

![API 集成](screenshots/349_plus0.0s.png)

Horde 提供了丰富的 API，可以获取更多信息：
- 变更列表描述
- 生成的构建产物
- 作业成功/失败状态
- 等等

![Markdown 支持](screenshots/354_plus0.0s.png)

Discord 支持 Markdown 语法，可以进一步美化消息。

本文展示的只是基础实现，您可以根据需求大幅扩展。

---

## 十二、总结与建议

### 12.1 最终部署架构

![最终架构](screenshots/359_plus0.0s.png)

我们成功构建了一个成本优化的 Horde 部署方案：

**云端组件：**
- 单个 EC2 实例（运行 Docker）
  - Horde 服务器
  - MongoDB
  - Redis
  - 控制面板
- Perforce 服务器
- S3 存储

**本地组件：**
- Build Agent
- Perforce Proxy

**第三方服务（免费）：**
- Auth0（认证）
- Discord（通知）

### 12.2 关键优势

![优势总结](screenshots/363_plus0.0s.png)

**1. 原生集成降低学习曲线**

尽管有学习曲线，但与通用 CI/CD 方案相比，Horde 针对 Unreal Engine 的原生集成大大降低了搭建管道的时间和精力投入。

**2. 流程简化**

![流程优势](screenshots/364_plus0.0s.png)

- 开箱即用的 BuildGraph 支持
- 无缝集成 Unreal GameSync
- 减少工具间的胶水代码

**3. 可扩展性**

![可扩展性](screenshots/366_plus0.0s.png)

虽然 Horde 为大规模设计，但也能以低成本部署，满足小团队需求。更重要的是，随着团队成长，可以平滑扩展。

**4. 适用于各种规模团队**

![适用性](screenshots/368_plus0.0s.png)

基于以上原因，我认为 Horde 实际上适合**几乎任何规模的团队**。

### 12.3 成本优化总结

**服务器成本：**
- 单个小规格 EC2 实例（本文示例：2核2GB）
- 注意：建议至少 4GB + Swap，避免内存问题

**存储成本：**
- S3 按需付费
- 利用预签名 URL 降低服务器负载

**构建资源成本：**
- 复用现有硬件作为 Agent
- 或购买硬件（一次性投资）

**第三方服务：**
- Auth0 免费额度充足（25,000 用户）
- Discord 完全免费

### 12.4 实用建议

**关于服务器规格**

![服务器配置](screenshots/392_plus0.0s.png)

我们使用 2核2GB 实例，但有一个前提：我们修改了 Horde 源码，限制了 Commit 对象存储的文件列表大小。

**推荐配置：**至少 **4GB 内存 + Swap 空间**

**关于版本兼容性**

![版本兼容性](screenshots/376_plus0.0s.png)

**Q：Horde 5.6 能用于早期版本的 Unreal 吗？**

**A：**最好使用相同版本，但：
- Horde 5.6 可以用于 5.5 和 5.4
- 5.3 会有问题（缺少 Artifact 元素），但可以回传

主要兼容性取决于 BuildGraph 版本。

**关于网络带宽**

![带宽问题](screenshots/411_plus0.0s.png)

我们没有遇到网络问题，主要因为：
- 使用 S3 预签名 URL
- Agent 直接与 S3 通信
- 避免了大文件通过 Horde 服务器中转

**唯一的瓶颈：**跨 Agent 的工作区水合（hydration）。文件需要上传到 S3 再下载到另一个 Agent，可能较慢。我们因此避免使用这个功能。

**关于云资源**

![云资源](screenshots/383_plus0.0s.png)

**Q：为什么不用 ECS 代替 EC2？**

**A：**主要是成本考虑。如果部署在多个实例上，ECS 更合适。但我们只有一台服务器，直接用 Docker 即可。

**Q：可以使用 AWS Spot 实例吗？**

![Spot 实例](screenshots/430_plus0.0s.png)

**A：**可以，Epic 可能就是这么做的（文档中有提及）。但需要注意工作区水合的开销。

**关于插件开发**

![插件学习](screenshots/399_plus0.0s.png)

**Q：如何学习 Horde 插件开发？**

**A：**文档只提到了插件系统的存在。最好的学习方法是参考 Horde 源码中已有的 6-7 个插件实现。

---

## 结语

![结语](screenshots/369_plus0.0s.png)

感谢阅读！希望这篇文章能帮助您的团队以经济实惠的方式部署 Horde。

**关键要点回顾：**
- Horde 不只适合大型团队
- 通过混合架构可以显著降低成本
- 利用免费的第三方服务（Auth0、Discord）
- Horde 的深度集成是其核心价值
- 插件系统提供了强大的扩展能力

**下一步建议：**
1. 评估您的团队是否适合 Horde
2. 规划您的流结构
3. 从最小化配置开始
4. 根据实际需求逐步优化

如有问题，欢迎在 Unreal 社区讨论！

---

## 附录：Q&A 精选

### Q1: 服务器是否需要 WAF 或 VPN 保护？

A: 我们只开放了必要的端口，主要依赖 Auth0 进行身份认证。没有额外的 WAF。

### Q2: Perforce Proxy 可以用 Commit 或 Edge Server 替代吗？

A: 可以。使用 Proxy 的主要目的是在本地网络与 Agent 一起运行，Commit/Edge Server 也能实现。

### Q3: Zen 是否可以与 Horde 集成用于 DDC 缓存共享？

A: 可以使用共享存储。当一个工作站构建了缓存后，可以通过 Horde 部署或复制到其他工作站。建议使用 Zen 和 Horde Compute 来优化。

---

**文章生成时间：** 2025-12-27  
**基于视频：** Horde on a Budget: Cost-Effective Infrastructure for Small Teams | Unreal Fest Bali 2025  
**总字数：** 约 15,000 字  
**截图引用：** 451 张（按需引用关键截图）

