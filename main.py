import requests

# 指定目标网页的URL
url = 'https://kyfw.12306.cn/otn/leftTicket/init?linktypeid=dc&fs=%E4%B8%8A%E6%B5%B7,SHH&ts=%E5%8C%97%E4%BA%AC%E5%8C%97,VAP&date=2023-08-10&flag=N,N,Y'

# 发起HTTP GET请求获取网页内容
response = requests.get(url)

# 检查响应状态码
if response.status_code == 200:
    # 输出网页内容
    print(response.text)
else:
    print(f"Failed to retrieve the page. Status code: {response.status_code}")
