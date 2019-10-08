'''
author  iyzyi
date    2019.10.07
不同网站的m3u8视频的下载基本相同，但是细节上不同（出于反下载的目的），使用时修改即可。
主要包括第一层m3u8选择清晰度，第二层m3u8获取ts链接，注意请求的host_url，具体网站具体分析。
然后多线程下载，注意ts文件的名称的确定。
有些网站性能不行，可以调低线程数。
'''

import requests, re, os, logging, threading


logging.basicConfig(level=logging.INFO,
                    format='[ %(levelname)s ] %(asctime)s %(filename)s:%(threadName)s:%(process)d:%(lineno)d %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filename='m3u8.log',
                    filemode='a')


class M3U8():
    def __init__(self, url, name, dir='test', thread_num=100, proxies=True):
        self.url = url
        self.name = name
        self.dir_path = dir
        if not os.path.exists(self.dir_path):
            os.makedirs(self.dir_path)
        self.thread_num = thread_num
        self.proxies = proxies
        self.rlock = threading.RLock()
        self.m3u8()


    #请求
    def request(self, url, msg, retry=5, timeout=10):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36'}
        if os.name == 'nt':    #windows
            proxies={'http': '127.0.0.1:1080', 'https': '127.0.0.1:1080'}    #ssr的win客户端采用1080端口的http协议
        elif os.name == 'posix':    #linux
            proxies={'http': '127.0.0.1:8118', 'https': '127.0.0.1:8118'}    #ssr+privoxy,通过privoxy将1080端口的socks协议转发给8118端口的http协议
        while retry > 0:
            try:
                if self.proxies:
                    r = requests.get(url, headers=headers, timeout=timeout, proxies=proxies)
                else:
                    r = requests.get(url, headers=headers, timeout=timeout)
            except Exception as e:
                logging.error(e, exc_info=True)
                print(e)
            else:
                if r:
                    return r
            retry -= 1
        print(msg)


    #返回最高清晰度的m3u8的链接
    def get_max_quality_link(self, host_url=''):
        if not re.search(r'^#EXTM3U', self.m3u8):
            print('1 请求到的内容并非m3u8格式')
        else:
            quality = re.finditer(r'(hls-(\d+)p.*?\.m3u8.*?)(\n|$)', self.m3u8)
            max_quality = max([int(i.group(2)) for i in quality])
            max_quality_link = re.search(r'(hls-{}p.*?\.m3u8.*?)(\n|$)'.format(max_quality), self.m3u8).group(1)
            if not host_url:
                host_url = os.path.split(self.url)[0] + '/'
            return host_url + max_quality_link


    #返回ts视频的url（列表形式）
    def get_ts_links(self, host_url=''):
        if not re.search(r'^#EXTM3U', self.max_quality_m3u8):
            print('2 请求到的内容并非m3u8格式')
        else:
            ts_tag = re.finditer(r'#EXTINF:.+?,\n(.+?)\n', self.max_quality_m3u8)
            if not host_url:
                host_url = os.path.split(self.max_quality_link)[0] + '/'
                #print(host_url)
            return [host_url + ts.group(1) for ts in ts_tag]
    

    def down_ts(self, ts_url):
        r = self.request(ts_url, msg='%s下载失败'%ts_url)
        if r:
            ts_name = os.path.split(ts_url)[1]
            ts_name = re.search('\d+?\.ts', ts_name).group()
            ts_name = ts_name.zfill(10) #前方补零至字符串总长度为10
            file_path = os.path.join(self.dir_path, ts_name)
            with open(file_path, 'ab') as f:
                f.write(r.content)
                f.flush()
            self.count += 1
            print("\r视频进度：%.2f%%" % (self.count/self.ts_num*100), end=' ')


    def thread_ts(self):
        while True:
            self.rlock.acquire()    #加线程锁，同一时间只能有一个线程运行此段代码
            if len(self.ts_links) == 0:
                self.rlock.release()    #释放线程锁
                break
            else:
                ts_url = self.ts_links.pop()
                self.rlock.release()    #释放线程锁
                self.down_ts(ts_url)


    def down_tss(self):
        thread_list = []
        self.count = 0
        self.ts_num = len(self.ts_links)
        for _ in range(self.thread_num):
            t = threading.Thread(target=self.thread_ts)
            thread_list.append(t)
            t.start()
        for t in thread_list:
            t.join()
        print()

    
    def check(self):
        if self.count == self.ts_num:
            return True
        else:
            print('部分ts文件下载失败')


    def merge(self):
        os.chdir(self.dir_path)
        cmd = "copy /b *.ts {}.mp4".format(self.name)
        os.system(cmd)
        os.system('del /Q *.ts')


    #主函数
    def m3u8(self):
        print('正在请求第一层m3u8')
        r = self.request(self.url, msg='m3u8请求失败')
        if r and r.text:
            self.m3u8 = r.text
            print(self.m3u8)
            self.max_quality_link = self.get_max_quality_link()
            print(self.max_quality_link)
            
            print('正在请求第二层m3u8')
            r = self.request(self.max_quality_link, msg='最高清晰度m3u8请求失败')
            if r and r.text:
                self.max_quality_m3u8 = r.text
                print(self.max_quality_m3u8)
                self.ts_links = self.get_ts_links('https://dan1.yyhdyl.com')
                #print(self.ts_links)

            print('正在请求ts文件')
            self.down_tss()
            if self.check():
                self.merge()


url = 'https://shuang2.yyhdyl.com/20190528/0f44f4c3f6ea693786ef3674822327cf/hls/hls.m3u8?t=1570495228&sign=4327deec6cb337b8f3006c6ff6575c87'
#url = 'https://vid-egc.xvideos-cdn.com/videos/hls/43/25/fc/4325fcce5dc4ff372569c8adf0801293/hls.m3u8?Agv62TMDw1cAMxRvP16ojVAaBEF-MPT4zZGoJO3LAWrjkRZ85v6wod2UlGyfNEB9lmq5dzN-Wg457cNIELlJwc7c7MNa7TSuKlzCWLS1KCQWso2EOiDKeCTO4QPf5_wExv3LTRhf0EzXqJaa8OHM-ifvkg'
m = M3U8(url, '测试', thread_num=4)