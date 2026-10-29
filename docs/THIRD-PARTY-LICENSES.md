# 第三方版权与许可

本安装包内包含以下第三方开源项目。请在遵守各自许可的前提下使用与分发。

## 1. xiaohongshu-skills

- 来源：https://github.com/autoclaw-cc/xiaohongshu-skills
- 基线提交：`b043748282a57e347c52f517dfb59819121134ab`
- 许可：MIT

```text
MIT License

Copyright (c) 2026 Auto-Claw-CC

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 2. Auto-Redbook-Skills

- 来源：https://github.com/comeonzhj/Auto-Redbook-Skills
- 基线提交：`da1c73a6624d1df1330e161663c3614753d4220b`
- 许可：MIT（上游仓库根目录没有 LICENSE 文件，许可信息写在 README 中）

README 中的许可声明：

```text
## 📄 License
MIT License © 2026
```

## 3. Python 运行时与依赖

包内不附带 Python 解释器与第三方 wheel，安装时由 uv / PyPI 下载，各自遵循其许可（多为 MIT / BSD / Apache-2.0）。
主要依赖：playwright（Apache-2.0）、markdown（BSD）、PyYAML（MIT）、greenlet（MIT）、pyee（MIT）、websockets（BSD）、requests（Apache-2.0）、python-socks（Apache-2.0）。

## 4. 本安装包自身的改动

`installer/`、`app/`、`skills/`、`docs/`、封面主题相关补丁由本项目作者提供，随上述两个上游项目一同分发。

