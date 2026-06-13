# 导入模块
import tkinter

# 创建主窗口
root = tkinter.Tk()
root.title("我的窗口")  # 窗口标题
root.geometry("300x200") # 窗口大小

# 添加文字标签
label = tkinter.Label(root, text="Hello Tkinter")
label.pack()

# 启动窗口循环（必须加，窗口才会显示）
root.mainloop()