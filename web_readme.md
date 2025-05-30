# MinerU PDF转换工具 - Gradio前端

这是MinerU PDF转换API服务的Gradio前端界面，提供了友好的Web UI来上传、转换和下载PDF文件。

## 功能特点

- 简洁直观的Web界面
- 上传PDF文件并转换为Markdown和JSON格式
- 查看任务处理状态
- 下载转换结果（单个文件或ZIP压缩包）
- 预览Markdown内容

## 安装

1. 确保已安装所有依赖
   ```bash
   pip install -r requirements.txt
   ```

2. 确保MinerU PDF转换API服务正在运行
   ```bash
   python run.py
   ```

3. 启动Gradio前端界面
   ```bash
   python web.py
   ```

## 使用方法

1. **上传PDF文件**
   - 点击"选择PDF文件"按钮上传PDF文件
   - 点击"上传并开始转换"按钮开始转换
   - 上传成功后，任务ID会自动填入状态查询框

2. **查看转换状态**
   - 输入任务ID（如果刚上传，会自动填入）
   - 点击"检查状态"按钮
   - 查看任务状态信息（处理中、完成或失败）

3. **下载转换结果**
   - 当任务完成后，"下载所有文件(ZIP)"按钮会显示
   - 点击下载ZIP压缩包，包含所有转换结果
   - 或者从下拉列表中选择单个文件下载

4. **预览Markdown内容**
   - 输入任务ID后，点击"预览Markdown内容"按钮
   - 界面会显示转换后的Markdown内容

## 配置

如需修改API服务地址，请编辑`web.py`文件中的`API_URL`变量：

```python
# API配置
API_URL = "http://localhost:8000"  # 修改为实际API地址
```

## 注意事项

- 确保API服务在Gradio前端启动前已经运行
- 大型PDF文件处理可能需要较长时间
- 任务结果会在服务器上保留24小时后自动删除

## 示例截图

![MinerU PDF转换工具界面](https://example.com/screenshot.png)

## 许可证

与MinerU相同，本项目采用AGPL-3.0许可证。 