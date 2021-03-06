# -*- coding: utf-8 -*-

from scapy.all import *          # 抓包软件
import time                      # 获取时间
import matplotlib.pyplot as plt  # 绘图
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import pandas as pd              # 绘图
from ui_Main_Window import *     # ui 文件导出的窗体界面
from PyQt5.QtWidgets import *    # PyQt5
from PyQt5.QtCore import QThread, pyqtSignal # 多线程，以及多线程之间传递信号
from network_monitor_no_gui import *

# class Figure_Canvas(FigureCanvas):   # 通过继承FigureCanvas类，使得该类既是一个PyQt5的Qwidget，又是一个matplotlib的FigureCanvas，这是连接pyqt5与matplot                                          lib的关键
#
#     def __init__(self, parent=None, width=110, height=50, dpi=100):
#         fig = Figure(figsize=(width, height), dpi=100)  # 创建一个Figure，注意：该Figure为matplotlib下的figure，不是matplotlib.pyplot下面的figure
#
#         FigureCanvas.__init__(self, fig) # 初始化父类
#         self.setParent(parent)
#
#         self.axes = fig.add_subplot(111) # 调用figure下面的add_subplot方法，类似于matplotlib.pyplot下面的subplot方法
#
#     def test(self):
#         x = [1,2,3,4,5,6,7,8,9]
#         y = [23,21,32,13,3,132,13,3,1]
#         self.axes.plot(x, y)
# 核心线程


SNIFF_INTERVAL = 0.5  # 一次抓包的时间


# 抓包线程
class SniffThread(QThread):
    trigger = pyqtSignal(PacketList)

    # 初始化函数
    def __init__(self, iface):
        super(SniffThread, self).__init__()
        self.iface = iface

    # 重写线程执行的run函数
    def run(self):
        packets = sniff(iface=self.iface, timeout=SNIFF_INTERVAL)
        self.trigger.emit(packets)  # 执行完成后触发 core_thread.sniff_finish()，之后进入 DataProcessThread


# 数据处理线程
class DataProcessThread(QThread):
    trigger = pyqtSignal(int)

    # 初始化函数
    def __init__(self, packets):
        super(DataProcessThread, self).__init__()
        self.packets = packets

    # 重写线程执行的run函数
    def run(self):
        packet_length = data_process(self.packets)
        self.trigger.emit(packet_length)  # 执行完成后触发 core_thread.data_process_finish()，之后进入 PlotThread


# 绘图线程
class PlotThread(QThread):
    # 初始化函数
    def __init__(self, main_ui, packet_length):
        super(PlotThread, self).__init__()
        self.main_ui = main_ui
        self.packet_length = packet_length

    # 重写线程执行的run函数
    def run(self):

        # 将速度换算为 K、M、G 的形式的字符串
        def speed2str(speed):
            unit = ['', 'K', 'M', 'G', 'T']
            _i = 0
            while speed >= 1000:
                speed /= 1024
                _i = _i + 1
            return '当前网速：' + '%.2f' % speed + unit[_i] + 'B/s'

        # 显示速度
        current_net_speed = self.packet_length / SNIFF_INTERVAL
        self.main_ui.NetspeedLabel.setText(speed2str(current_net_speed))

        QApplication.processEvents()  # 刷新界面
        return


class CoreThread(QThread):

    # 初始化函数
    def __init__(self, main_ui):
        super(CoreThread, self).__init__()
        self.main_ui = main_ui
        self.iface = ''
        self.userIP = ''
        self.sniff_thread = None
        self.data_process_thread = None
        self.plot_thread = None

    # 重写线程执行的run函数
    def run(self):
        init_database(self.userIP)
        plt.ion()

        while True:
            # 检测监测网卡是否有变化
            network_info_str = self.main_ui.PopupInterface.currentText()
            network_info = network_info_str.strip('][').replace('\'','').split(', ')
            if network_info[0] != self.iface:
                init_database(self.userIP)
                self.iface = network_info[0]
                self.userIP = network_info[1]

            if self.sniff_thread is not None:
                self.sniff_thread.wait()  # 等待上一抓包线程结束
            self.sniff_thread = SniffThread(self.iface)
            self.sniff_thread.start()
            self.sniff_thread.trigger.connect(self.sniff_finished)
            # QApplication.processEvents()  # 刷新界面

    def sniff_finished(self, packets):
        self.data_process_thread = DataProcessThread(packets)
        self.data_process_thread.start()
        self.data_process_thread.trigger.connect(self.data_process_finished)

    def data_process_finished(self, packet_length):
        self.plot_thread = PlotThread(self.main_ui, packet_length)
        self.plot_thread.start()


class NetworkMonitorMainUI(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(NetworkMonitorMainUI, self).__init__(parent)
        self.setupUi(self)
        # 四个单选框的信号与槽，将单击单选框行为和函数关联起来
        self.RadioButtonIP.clicked.connect(self.radio_button_ip_click)
        self.RadioButtonProtocol.clicked.connect(self.radio_button_protocol_click)
        self.RadioButtonPacket.clicked.connect(self.radio_button_packet_click)
        self.RadioButtonLength.clicked.connect(self.radio_button_length_click)
        # 设置选择网卡的下拉菜单栏
        for i in get_network_info():
            self.PopupInterface.addItem(str[i])
        self.core = CoreThread(self)
        self.core.start()
        self.show()

    # 单击对应单选框后触发的四个函数
    def radio_button_ip_click(self):
        self.RadioButtonProtocol.setChecked(False)  # 将另外一个按钮置零

    def radio_button_protocol_click(self):
        self.RadioButtonIP.setChecked(False)

    def radio_button_packet_click(self):
        self.RadioButtonLength.setChecked(False)

    def radio_button_length_click(self):
        self.RadioButtonPacket.setChecked(False)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_ui = NetworkMonitorMainUI()
    main_ui.show()
    sys.exit(app.exec_())
