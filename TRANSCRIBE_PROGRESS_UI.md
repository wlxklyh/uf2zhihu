# 语音转录UI进度显示功能 - 实现文档

## 功能概述

为语音转录步骤（Step 2）添加了类似视频下载的UI进度显示功能，包括实时进度百分比、转录速度、已用时间、预计剩余时间等详细信息。

## 修改文件列表

### 1. 后端修改

#### `src/core/steps/step2_transcribe.py`

**主要修改：**

1. **增强进度监控循环** (`_progress_monitor_loop`)
   - 添加了详细进度更新机制，每5秒发送一次详细进度
   - 原有的心跳日志保持30秒间隔（可配置）
   - 支持发送详细进度数据到Web界面

2. **新增方法** `_build_detailed_progress()`
   - 构建详细的进度数据字典
   - 包含以下字段：
     * `percent`: 进度百分比（0-95）
     * `speed`: 转录速度（相对于实时播放，如 "6.67x"）
     * `elapsed`: 已用时间（格式化为易读形式，如 "2分30秒"）
     * `eta`: 预计剩余时间（格式化为易读形式）
     * `processed`: 已处理视频时长（如 "5:30"）
     * `total`: 视频总时长（如 "8:00"）
     * `model`: 使用的Whisper模型（如 "base"）
     * `language`: 目标语言（如 "en"）

3. **优化进度计算** (`_calculate_estimated_progress`)
   - 返回更完整的进度信息
   - 添加 `estimated_total` 字段

#### `src/core/processor.py`

**主要修改：**

1. **添加转录进度回调**
   - 新增 `transcribe_progress_callback` 属性
   - 更新 `set_callbacks()` 方法支持转录进度回调
   - 新增 `_send_transcribe_progress()` 方法

2. **修改步骤2执行逻辑** (`_execute_step2`)
   - 定义转录进度回调函数
   - 将回调函数传递给 `AudioTranscriber`
   - 通过回调实时发送转录进度到Web界面

#### `src/web/app.py`

**主要修改：**

1. **添加转录进度处理函数** `send_transcribe_progress()`
   - 通过 SocketIO 发送 `transcribe_progress` 事件
   - 包含项目名称、步骤号、进度数据和时间戳

2. **注册转录进度回调**
   - 在 `create_app()` 中调用 `processor.set_callbacks()` 时添加转录进度回调

### 2. 前端修改

#### `src/web/templates/process.html`

**主要修改：**

1. **添加转录进度UI容器** (`transcribeProgressContainer`)
   ```html
   - 进度条（蓝色主题，区别于下载进度的绿色）
   - 4个主要指标显示：
     * 转录速度
     * 已用时间
     * 预计剩余时间
     * 进度（已处理/总时长）
   - 模型信息显示：
     * 使用的模型
     * 目标语言
   ```

2. **添加JavaScript事件处理**
   - 监听 `transcribe_progress` Socket.IO 事件
   - 实现 `updateTranscribeProgress()` 函数更新UI
   - 在 `setActiveStep()` 中控制转录进度容器的显示/隐藏

### 3. 配置文件修改

#### `config/config.ini`

**新增配置项：**

```ini
[step2_transcribe]
progress_update_interval = 5        # 详细进度更新间隔（秒）
show_detailed_progress = true       # 是否显示详细进度
```

## 功能特点

### 1. 实时进度更新

- **更新频率**: 每5秒更新一次详细进度（可配置）
- **心跳日志**: 每30秒输出一次日志（可配置）
- **自动超时检测**: 基于配置的超时系数自动检测转录超时

### 2. 转录速度计算

转录速度计算公式：
```
转录速度 = (已处理视频时长) / (实际用时)
```

例如：
- 1分钟的视频用了9秒转录 → 速度 = 6.67x（比实时快6.67倍）
- 显示为 "6.67x"

### 3. 时间格式化

智能时间格式化：
- 小于1分钟: "45秒"
- 1-60分钟: "2分30秒"
- 超过1小时: "1小时25分"

### 4. UI设计

- **视觉区分**: 转录进度使用蓝色主题（`bg-info`），下载进度使用绿色主题
- **自动显示**: 进入步骤2时自动显示，其他步骤自动隐藏
- **响应式布局**: 支持桌面和移动设备

## 数据流程

```
AudioTranscriber._progress_monitor_loop()
    ↓
    计算进度 (_calculate_estimated_progress)
    ↓
    构建详细数据 (_build_detailed_progress)
    ↓
    调用 progress_callback (转录进度回调函数)
    ↓
processor._send_transcribe_progress()
    ↓
app.send_transcribe_progress()
    ↓
    SocketIO.emit('transcribe_progress')
    ↓
前端 socket.on('transcribe_progress')
    ↓
updateTranscribeProgress() 更新UI
```

## 测试建议

### 1. 功能测试

1. **正常流程测试**
   - 启动一个视频处理任务
   - 观察步骤2（语音转录）的进度显示
   - 验证以下数据是否正常显示：
     * 进度百分比
     * 转录速度
     * 已用时间
     * 预计剩余时间
     * 已处理/总时长
     * 模型信息
     * 语言信息

2. **边界测试**
   - 测试非常短的视频（<30秒）
   - 测试较长的视频（>10分钟）
   - 测试不同的Whisper模型（tiny, base, small, medium, large）

3. **缓存测试**
   - 测试使用缓存的字幕时是否正常跳过进度显示
   - 验证第二次处理同一视频时的行为

### 2. 性能测试

1. **进度更新频率**
   - 验证进度更新不会过于频繁（默认5秒一次）
   - 确认不会因频繁更新导致UI卡顿

2. **内存使用**
   - 监控长时间转录时的内存使用情况
   - 确保监控线程正确清理

### 3. UI测试

1. **响应式测试**
   - 在不同屏幕尺寸下测试UI显示
   - 验证移动设备上的显示效果

2. **浏览器兼容性**
   - 测试主流浏览器（Chrome, Firefox, Edge, Safari）
   - 验证 SocketIO 连接的稳定性

## 配置优化建议

根据实际使用情况，可以调整以下配置：

### 转录速度系数 (`transcribe_speed_factor`)

- **当前值**: 0.15（即转录时间约为视频时长的15%）
- **建议调整**:
  * Whisper tiny 模型: 0.05-0.08
  * Whisper base 模型: 0.10-0.15
  * Whisper small 模型: 0.15-0.25
  * Whisper medium 模型: 0.25-0.40
  * Whisper large 模型: 0.40-0.60

### 进度更新间隔 (`progress_update_interval`)

- **当前值**: 5秒
- **建议调整**:
  * 快速转录（<5分钟视频）: 2-3秒
  * 正常转录: 5秒（默认）
  * 长视频转录: 10秒

### 心跳日志间隔 (`progress_heartbeat_interval`)

- **当前值**: 30秒
- **建议调整**:
  * 开发/调试环境: 15-30秒
  * 生产环境: 30-60秒

## 已知限制

1. **进度估算基于时间**
   - Whisper API 不提供实时进度信息
   - 进度基于视频时长和转录速度系数估算
   - 实际进度可能与显示进度有偏差

2. **最大显示进度为95%**
   - 为避免显示100%但转录未完成的情况
   - 完成后会立即更新为100%

3. **转录速度动态变化**
   - 不同视频片段的转录速度可能不同
   - 显示的速度是平均值

## 后续优化方向

1. **进度精确度提升**
   - 研究是否可以从Whisper获取更精确的进度信息
   - 考虑基于音频分段提供更准确的进度

2. **用户体验优化**
   - 添加转录质量预览
   - 显示置信度评分
   - 添加暂停/取消转录功能

3. **性能优化**
   - 支持GPU加速时的进度追踪
   - 优化长视频的内存使用

## 版本信息

- **创建日期**: 2025-12-28
- **版本**: 1.0.0
- **作者**: AI Assistant
- **测试状态**: 待测试

