# 适用于小米手环七的图像转换工具
在两年前就已经有人发了电脑端的这个工具，但迟迟不见有手机端的，虽然有一些人的确找到了解决方案，但是目前网络上的转换工具鱼龙混杂，一些萌新根本搞不懂，现在的情形非常需要一个手机端转换工具，于是就有了本程序。

# 有什么不同
与电脑端的不同，我们这个工具完全依赖终端进行操作，千万不要感觉麻烦，非常简单，接下来进行详细教程：

# 使用步骤
1.首先你需要一个Termux。(链接:(https://github.com/termux/termux-app/releases/tag/v0.118.1 )

2.安装完毕之后，给予Termux存储权限，命令为:termux-setup-storage，接着你会发现它停在了这里：Do you want to continue? (y/n)，你只需要输入y并回车即可。

3.接下来请前往自己的MT管理器，找到/storage/Pictures/这个路径(不同手机的可能有点不一样，这里不予区分教程，网上一抓一大把)，你将会看到一堆文件夹，当然你要选择进行转换的图像也在这里面，接下来你只需要耐心的找，找到之后长按图像文件，把图像文件从这里复制到下载的文件所处的目录中。

4.完成了这一切之后你就可以返回终端输入下载的文件所处路径了：
```bash
cd+空格+复制的目录
```
进入目录后，安装需要安装的依赖：
```bash
apt update && apt upgrade
pkg install python
pkg install python-pillow
```
全部安装完成后输入以下命令：
```bash
python 4.py (复制的图像文件名)
```

就会输出文件到4.py所处的目录里

# 注意事项
下载的4.py文件和需要转换格式的图片要处在同一目录下！

# 赞助/了解新产品
1. [DL报刊论坛](https://afdian.com/a/dlbaokanluntanos)

2.[番茄小说下载器精简版](https://github.com/Dlmily/Tomato-Novel-Downloader-Lite)

# 其他
~`致谢`：@H!Mooo

~[参考代码](https://github.com/p149u3/MiBand7Tools)
