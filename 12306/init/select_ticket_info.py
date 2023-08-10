# -*- coding=utf-8 -*-
import datetime
import random
import os
import socket
import sys
import threading
import time
import TickerConfig
import wrapcache
from agency.cdn_utils import CDNProxy, open_cdn_file
from config import urlConf, configCommon
from config.TicketEnmu import ticket
from config.configCommon import seat_conf_2, seat_conf
from config.getCookie import getDrvicesID
from init.login import GoLogin
from inter.AutoSubmitOrderRequest import autoSubmitOrderRequest
from inter.ChechFace import chechFace
from inter.CheckUser import checkUser
from inter.GetPassengerDTOs import getPassengerDTOs
from inter.LiftTicketInit import liftTicketInit
from inter.Query import query
from inter.SubmitOrderRequest import submitOrderRequest
from myException.PassengerUserException import PassengerUserException
from myException.UserPasswordException import UserPasswordException
from myException.ticketConfigException import ticketConfigException
from myException.ticketIsExitsException import ticketIsExitsException
from myException.ticketNumOutException import ticketNumOutException
from myUrllib.httpUtils import HTTPClient


class select:
    """
    快速提交车票通道
    """
    def __init__(self):
        self.cdn_list = open_cdn_file("filter_cdn_list")
        self.get_ticket_info()
        self._station_seat = [seat_conf[x] for x in TickerConfig.SET_TYPE]
        self.auto_code_type = TickerConfig.AUTO_CODE_TYPE
        self.httpClint = HTTPClient(TickerConfig.IS_PROXY, self.cdn_list)
        self.httpClint.cdn = self.cdn_list[random.randint(0, 4)]
        self.urls = urlConf.urls
        self.login = GoLogin(self, TickerConfig.IS_AUTO_CODE, self.auto_code_type)
        self.cookies = ""
        self.queryUrl = "leftTicket/queryO"
        self.passengerTicketStrList = ""
        self.passengerTicketStrByAfterLate = ""
        self.oldPassengerStr = ""
        self.set_type = ""
        self.flag = True

    @staticmethod
    def get_ticket_info():
        """
        获取配置信息
        :return:
        """

        print(u"*" * 50)
        print(f"检查当前版本为: {TickerConfig.RE_VERSION}")
        version = sys.version.split(" ")[0]
        print(u"检查当前python版本为：{}，目前版本只支持3.6以上".format(version))
        if version < "3.6.0":
            raise Exception
        print(u"12306刷票小助手，最后更新于2019.09.18，请勿作为商业用途，交流群号："
              u" 1群：286271084(已满)\n"
              u" 2群：649992274(已满)\n"
              u" 3群：632501142(已满)\n"
              u" 4群: 606340519(已满)\n"
              u" 5群: 948526733(已满)\n"
              u" 7群: 660689659(已满)\n"
              u" 8群: 620629239(已满)\n"
              u" 6群: 608792930(未满)\n"
              u" 9群: 693035807(未满)\n"
              )
        print(
            f"当前配置：\n出发站：{TickerConfig.FROM_STATION}\n到达站：{TickerConfig.TO_STATION}\n车次: {','.join(TickerConfig.STATION_TRAINS) or '所有车次'}\n乘车日期：{','.join(TickerConfig.STATION_DATES)}\n坐席：{','.join(TickerConfig.SET_TYPE)}\n是否有票优先提交：{TickerConfig.IS_MORE_TICKET}\n乘车人：{TickerConfig.TICKET_PEOPLES}\n" \
            f"刷新间隔: 随机(1-3S)\n僵尸票关小黑屋时长: {TickerConfig.TICKET_BLACK_LIST_TIME}\n下单接口: {TickerConfig.ORDER_TYPE}\n下单模式: {TickerConfig.ORDER_MODEL}\n预售踩点时间:{TickerConfig.OPEN_TIME}")
        print(u"*" * 50)

    def station_table(self, from_station, to_station):
        """
        读取车站信息
        :param station:
        :return:
        """
        path = os.path.join(os.path.dirname(__file__), '../station_name.txt')
        try:
            with open(path, encoding="utf-8") as result:
                info = result.read().split('=')[1].strip("'").split('@')
        except Exception:
            with open(path) as result:
                info = result.read().split('=')[1].strip("'").split('@')
        del info[0]
        station_name = {}
        for i in range(0, len(info)):
            n_info = info[i].split('|')
            station_name[n_info[1]] = n_info[2]
        try:
            from_station = station_name[from_station.encode("utf8")]
            to_station = station_name[to_station.encode("utf8")]
        except KeyError:
            from_station = station_name[from_station]
            to_station = station_name[to_station]
        return from_station, to_station

    def call_login(self, auth=False):
        """
        登录回调方法
        :return:
        """
        if auth:
            return self.login.auth()
        else:
            configCommon.checkSleepTime(self)  # 防止网上启动晚上到点休眠
            self.login.go_login()

    def main(self):
        l = liftTicketInit(self)
        l.reqLiftTicketInit()
        getDrvicesID(self)
        self.call_login()
        check_user = checkUser(self)
        t = threading.Thread(target=check_user.sendCheckUser)
        t.setDaemon(True)
        t.start()
        from_station, to_station = self.station_table(TickerConfig.FROM_STATION, TickerConfig.TO_STATION)
        num = 0
        s = getPassengerDTOs(selectObj=self, ticket_peoples=TickerConfig.TICKET_PEOPLES)
        passenger = s.sendGetPassengerDTOs()
        wrapcache.set("user_info", passenger, timeout=9999999)

        now = datetime.datetime.now()
        if TickerConfig.ORDER_MODEL is 1:
            print(f"预售还未开始，阻塞中，预售时间为{TickerConfig.OPEN_TIME}, 当前时间为: {now.strftime('%H:%M:%S')}")
            sleep_time_s = 0.1
            sleep_time_t = 0.3
            # 测试了一下有微妙级的误差，应该不影响，测试结果：2019-01-02 22:30:00.004555，预售还是会受到前一次刷新的时间影响，暂时没想到好的解决方案
            while now.strftime("%H:%M:%S") < TickerConfig.OPEN_TIME:
                now = datetime.datetime.now()
                time.sleep(0.0001)
            print(f"预售开始，开启时间为: {now.strftime('%H:%M:%S')}")
        else:
            sleep_time_s = TickerConfig.MIN_TIME
            sleep_time_t = TickerConfig.MAX_TIME

        while 1:
            try:
                num += 1
                now = datetime.datetime.now()  # 感谢群里大佬提供整点代码
                configCommon.checkSleepTime(self)  # 晚上到点休眠
                q = query(selectObj=self,
                          from_station=from_station,
                          to_station=to_station,
                          from_station_h=TickerConfig.FROM_STATION,
                          to_station_h=TickerConfig.TO_STATION,
                          _station_seat=self._station_seat,
                          station_trains=TickerConfig.STATION_TRAINS,
                          station_dates=TickerConfig.STATION_DATES,
                          ticke_peoples_num=len(TickerConfig.TICKET_PEOPLES),
                          )
                queryResult = q.sendQuery()
                # 查询接口
                if queryResult.get("status"):
                    train_no = queryResult.get("train_no", "")
                    train_date = queryResult.get("train_date", "")
                    stationTrainCode = queryResult.get("stationTrainCode", "")
                    secretStr = queryResult.get("secretStr", "")
                    secretList = queryResult.get("secretList", "")
                    seat = queryResult.get("seat", "")
                    leftTicket = queryResult.get("leftTicket", "")
                    query_from_station_name = queryResult.get("query_from_station_name", "")
                    query_to_station_name = queryResult.get("query_to_station_name", "")
                    is_more_ticket_num = queryResult.get("is_more_ticket_num", len(TickerConfig.TICKET_PEOPLES))
                    if wrapcache.get(train_no):
                        print(ticket.QUEUE_WARNING_MSG.format(train_no))
                    else:
                        # 获取联系人
                        s = getPassengerDTOs(selectObj=self, ticket_peoples=TickerConfig.TICKET_PEOPLES,
                                             set_type="" if isinstance(seat, list) else seat_conf_2[seat],
                                             # 候补订单需要设置多个坐席
                                             is_more_ticket_num=is_more_ticket_num)
                        getPassengerDTOsResult = s.getPassengerTicketStrListAndOldPassengerStr(secretStr, secretList)
                        if getPassengerDTOsResult.get("status", False):
                            self.passengerTicketStrList = getPassengerDTOsResult.get("passengerTicketStrList", "")
                            self.passengerTicketStrByAfterLate = getPassengerDTOsResult.get(
                                "passengerTicketStrByAfterLate", "")
                            self.oldPassengerStr = getPassengerDTOsResult.get("oldPassengerStr", "")
                            self.set_type = getPassengerDTOsResult.get("set_type", "")
                        # 提交订单
                        # 订单分为两种，一种为抢单，一种为候补订单
                        if secretStr:  # 正常下单
                            if TickerConfig.ORDER_TYPE == 1:  # 快速下单
                                a = autoSubmitOrderRequest(selectObj=self,
                                                           secretStr=secretStr,
                                                           train_date=train_date,
                                                           passengerTicketStr=self.passengerTicketStrList,
                                                           oldPassengerStr=self.oldPassengerStr,
                                                           train_no=train_no,
                                                           stationTrainCode=stationTrainCode,
                                                           leftTicket=leftTicket,
                                                           set_type=self.set_type,
                                                           query_from_station_name=query_from_station_name,
                                                           query_to_station_name=query_to_station_name,
                                                           )
                                a.sendAutoSubmitOrderRequest()
                            elif TickerConfig.ORDER_TYPE == 2:  # 普通下单
                                sor = submitOrderRequest(self, secretStr, from_station, to_station, train_no,
                                                         self.set_type,
                                                         self.passengerTicketStrList, self.oldPassengerStr, train_date,
                                                         TickerConfig.TICKET_PEOPLES)
                                sor.sendSubmitOrderRequest()
                        elif secretList:  # 候补订单
                            c = chechFace(self, secretList, train_no)
                            c.sendChechFace()
                else:
                    random_time = round(random.uniform(sleep_time_s, sleep_time_t), 2)
                    nateMsg = ' 无候补机会' if TickerConfig.ORDER_TYPE == 2 else ""
                    print(f"正在第{num}次查询 停留时间：{random_time} 乘车日期: {','.join(TickerConfig.STATION_DATES)} 车次：{','.join(TickerConfig.STATION_TRAINS) or '所有车次'} 下单无票{nateMsg} 耗时：{(datetime.datetime.now() - now).microseconds / 1000} {queryResult.get('cdn')}")
                    time.sleep(random_time)
            except PassengerUserException as e:
                print(e)
                break
            except ticketConfigException as e:
                print(e)
                break
            except ticketIsExitsException as e:
                print(e)
                break
            except ticketNumOutException as e:
                print(e)
                break
            except UserPasswordException as e:
                print(e)
                break
            except ValueError as e:
                if e == "No JSON object could be decoded":
                    print(u"12306接口无响应，正在重试")
                else:
                    print(e)
            except KeyError as e:
                print(e)
            except TypeError as e:
                print(u"12306接口无响应，正在重试 {0}".format(e))
            except socket.error as e:
                print(e)


if __name__ == '__main__':
    s = select()
    cdn = s.station_table("长沙", "深圳")
