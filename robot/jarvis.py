# coding=utf-8
import ConfigParser
import datetime
import json
import logging
import time
import urllib2
from logging import config

from IronManSuits.suits import MarkI
from weapons import db


class Jarvis:
    """
    Jarvis 可以制作和管理许多suit 
    每个suit可以获取天气信息 分析 等等……
    """

    def __init__(self, config_path='config/config.ini'):
        conf = ConfigParser.ConfigParser()
        conf.read(config_path)
        if not conf.sections():
            exit(1)
        self.conf = conf
        self.db = db.get_db_Session(conf=conf)
        self.city_list_redis = db.get_redis_conn(conf=conf, db=self.conf.get('misc', 'city_list_redis'))
        self.weather_data_redis = db.get_redis_conn(conf=conf, db=self.conf.get('misc', 'weather_data'))

    def search_provinces(self):
        prov_req = urllib2.Request('http://www.weather.com.cn/data/city3jdata/china.html')
        prov_req.add_header('Referer', 'http://www.weather.com.cn/pubmodel/inquires2.htm')
        data = urllib2.urlopen(prov_req)
        provs = json.loads(data.read())
        for prov_no in provs:
            self.city_list_redis.set(
                'china_{prov_no}'.format(prov_no=prov_no), provs[prov_no],
                ex=self.conf.getint('misc', 'city_list_expires'))
        # print {prov_id: self.city_list_redis.get(prov_id) for prov_id in self.city_list_redis.keys('prov_*')}
        for prov_no in provs:
            self.search_cities(prov_no)

    def search_cities(self, prov_no):
        """
        search_cities 结构最为复杂 因为涉及到直辖市 和 普通的省市结构
        对于省市结构的模型 直接根据省查找市 根据市查找区 flag = 0 city_101PPCC (特征是city_7位)
        对于直辖市结构模型 直接根据省查找站 把站id存入 flag = 1 city_101PPSS00 (特征是city_9位)
        
        :param prov_no: 
        :return: 
        """
        city_req = urllib2.Request(
            'http://www.weather.com.cn/data/city3jdata/provshi/{prov_no}.html'.format(prov_no=prov_no))
        city_req.add_header('Referer', 'http://www.weather.com.cn/pubmodel/inquires2.htm')
        data = urllib2.urlopen(city_req)
        cities = json.loads(data.read())

        for city_no in cities:
            if len(cities) == 1:
                self.search_stations(prov_no, city_no, flag=1)
            else:
                self.city_list_redis.set(
                    'city_{prov_no}_{city_no}'.format(prov_no=prov_no, city_no=city_no),
                    cities[city_no],
                    self.conf.getint('misc', 'city_list_expires')
                )
                self.search_stations(prov_no, city_no, flag=0)

    def search_stations(self, prov_no, city_no, flag=0):

        station_req = urllib2.Request(
            'http://www.weather.com.cn/data/city3jdata/station/{0}{1}.html'.format(prov_no, city_no))
        station_req.add_header('Referer', 'http://www.weather.com.cn/pubmodel/inquires2.htm')
        data = urllib2.urlopen(station_req)
        stations = json.loads(data.read())
        if flag == 0:
            for station_no in stations:
                if len(station_no) == 2:
                    self.city_list_redis.set(
                        'station_{prov_no}_{city_no}_{prov_no}{city_no}{station_no}'.format(
                            prov_no=prov_no, city_no=city_no, station_no=station_no),
                        stations[station_no],
                        self.conf.getint('misc', 'city_list_expires')
                    )
                    self.city_list_redis.set(
                        'list_{prov_no}{city_no}{station_no}'.format(
                            prov_no=prov_no, city_no=city_no, station_no=station_no),
                        stations[station_no],
                        self.conf.getint('misc', 'city_list_expires')
                    )

                else:
                    self.city_list_redis.set(
                        'station_{prov_no}_{city_no}_{station_no}'.format(
                            prov_no=prov_no, city_no=city_no, station_no=station_no),
                        stations[station_no],
                        self.conf.getint('misc', 'city_list_expires')
                    )
                    self.city_list_redis.set(
                        'list_{station_no}'.format(station_no=station_no),
                        stations[station_no],
                        self.conf.getint('misc', 'city_list_expires')
                    )
        elif flag == 1:
            for station_no in stations:
                if len(station_no) == 2:
                    self.city_list_redis.set(
                        'station_{prov_no}_{prov_no}{station_no}{city_no}'.format(
                            prov_no=prov_no, city_no=city_no, station_no=station_no),
                        stations[station_no],
                        self.conf.getint('misc', 'city_list_expires'))
                    self.city_list_redis.set(
                        'list_{prov_no}{station_no}{city_no}'.format(
                            prov_no=prov_no, city_no=city_no, station_no=station_no),
                        stations[station_no],
                        self.conf.getint('misc', 'city_list_expires')
                    )
                else:
                    self.city_list_redis.set(
                        'station_{prov_no}_{station_no}'.format(prov_no=prov_no, station_no=station_no),
                        stations[station_no],
                        self.conf.getint('misc', 'city_list_expires')
                    )
                    self.city_list_redis.set(
                        'list_{station_no}'.format(station_no=station_no),
                        stations[station_no],
                        self.conf.getint('misc', 'city_list_expires')
                    )

    def suit_maker(self):
        city_ids = self.city_list_redis.keys('list_*')
        logging.info('天气爬取任务启动')
        t = time.time()
        for city_id in city_ids:
            try:
                city = MarkI(city_id=int(city_id.split('_')[1]), conf=self.conf)
            except ValueError as e:
                logging.error('{city_id} 生成对象时发生错误。{e}'.format(city_id=city_id, e=e))
                continue
            res = city.get_data()
            if res is not True:
                logging.error('{city_id}get_data 返回false: {res}'.format(
                    city_id=city_id, res=res))
        logging.info('天气爬取任务结束。耗时:{time:.2f}s，爬取{count}个城市'.format(time=time.time() - t, count=len(city_ids)))

    def run(self):
        start = time.time()
        if datetime.datetime.now().hour == 0 or self.conf.getboolean('misc', 'debug') or len(
                self.city_list_redis.keys('list_*')) < 2000:
            logging.info('同步城市结构启动')
            self.search_provinces()
            logging.info('同步城市结构结束 {time:.2f}s'.format(time=time.time() - start))
        self.suit_maker()


if __name__ == '__main__':
    logging.config.fileConfig('config/log.conf')
    logging.info('爬虫定时任务启动')
    j = Jarvis()
    j.run()
