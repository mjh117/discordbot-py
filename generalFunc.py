import datetime, json, os, re, requests, base64

GIT_AUTH = os.environ['GIT_AUTH']
GIT_URL = os.environ['GIT_URL']

def getTime():
  tz = datetime.timezone(datetime.timedelta(hours=9))
  cur_time = datetime.datetime.now(tz=tz).strftime('%H:%M')
  return cur_time

def getDate():
  tz = datetime.timezone(datetime.timedelta(hours=9))
  cur_date = datetime.datetime.now(tz=tz).strftime('%y-%m-%d')
  return cur_date

def getMedal(day_num : int):
  if day_num<10 :  medal = ":third_place:"
  elif day_num<30 : medal = ":second_place:"
  elif day_num<66 : medal = ":first_place:"
  elif day_num>=66 : medal = ":medal:"
  return medal

def checkVal(type:str, value:str):
  if type=="date":
    if not bool(re.match(r"^\d{2}-\d{2}-\d{2}$", value)) :
      return f"{value}(X) 날짜를 yy-dd-mm 형식으로 입력해주세요."
    dNum = value.split("-")
    if int(dNum[1])<0 or int(dNum[1])>12 or int(dNum[2])<0 or int(dNum[2])>31:
      return f"{value}(X) 범위 내의 날짜를 입력해주세요."
  if type=="time":
    if not bool(re.match(r"^\d{2}:\d{2}$", value)) :
      return f"{value}(X) 시간을 hh:mm 형식으로 입력해주세요."
    tNum = value.split(":")
    if int(tNum[0])<0 or int(tNum[0])>23 or int(tNum[1])<0 or  int(tNum[1])>59 :
      return f"{value}(X) 범위 내의 시간을 입력해주세요."
  return None

def saveRemote(data : dict):
  #깃헙 백업
  try:
    mem_dic = data
    url = GIT_URL
    headers = {'Authorization': 'Bearer ' + GIT_AUTH}
    content = base64.b64encode(json.dumps(mem_dic, indent=4, ensure_ascii=False).encode()).decode()
    r = requests.get(url, headers=headers)
    sha = r.json()['sha']
    now = getDate() + " " + getTime()
    r = requests.put(url, json={'message': f'Backup json file({now})', 'sha': sha, 'content':content}, headers=headers)
    status = r.status_code
    if status == 200:
      msg= f"[{status}]Saved Data of {len(mem_dic)} Members"
    else :
      msg = f"[{status}]Faild to save data in remote"
  except Exception as e:
    print(e)
    msg = f"[except]Faild to save data in remote({e})"
  finally:
    return msg