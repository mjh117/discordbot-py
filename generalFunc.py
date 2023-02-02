import datetime, json, os, re, requests, base64

GIT_AUTH = os.environ['GIT_AUTH']
GIT_URL = os.environ['GIT_URL'] #로컬/원격 URL 분리
BACKUP_FILE = os.environ['BACKUP_FILE'] #로컬/원격 파일 분리

def getTime(utc_hour:int=9):
  tz = datetime.timezone(datetime.timedelta(hours=utc_hour))
  cur_time = datetime.datetime.now(tz=tz).strftime('%H:%M')
  return cur_time

def getDate():
  tz = datetime.timezone(datetime.timedelta(hours=9))
  cur_date = datetime.datetime.now(tz=tz).strftime('%y-%m-%d')
  return cur_date

def getMedal(day_num : int):
  if day_num== -1 : medal = ':sparkles:'
  elif day_num>=0 and day_num<10 :  medal = ":third_place:"
  elif day_num<30 : medal = ":second_place:"
  elif day_num<66 : medal = ":first_place:"
  elif day_num>=66 : medal = ":medal:"
  return medal

#자동 생성시 해외거주 체크
def checkAbroad(mem_dic:dict, userId:str):
  utc_hour = 9
  if "utc_hour" in mem_dic[userId] :
    utc_hour = mem_dic[userId]["utc_hour"]
  timeStr = getTime(utc_hour)
  return timeStr

#수동 입력시 형식 체크
def checkVal(type:str, value:str):
  if type=="date":
    if not bool(re.match(r"^\d{2}-\d{2}-\d{2}$", value)) :
      return f"{value}(X) 날짜를 yy-mm-dd 형식(ex.23-01-15)으로 입력해주세요."
    dNum = value.split("-")
    if int(dNum[1])<0 or int(dNum[1])>12 or int(dNum[2])<0 or int(dNum[2])>31:
      return f"{value}(X) 범위 내의 날짜를 입력해주세요."
  if type=="time":
    if not bool(re.match(r"^\d{2}:\d{2}$", value)) :
      return f"{value}(X) 시간을 hh:mm(ex.05:30) 형식으로 입력해주세요."
    tNum = value.split(":")
    if int(tNum[0])<0 or int(tNum[0])>23 or int(tNum[1])<0 or  int(tNum[1])>59 :
      return f"{value}(X) 범위 내의 시간을 입력해주세요."
  return None #정상 입력

#체크인 데이터 로컬에서 읽어오기
def readLocal():
  mem_dic = {}
  try:
    with open(BACKUP_FILE, "rt", encoding="utf-8") as fp:
      mem_dic = json.load(fp)
    msg = f"[readLocal]Total number of members: {len(mem_dic)}"
  except Exception as e:
    msg = f"[readLocal:E]Faild to read data from remote({e})"
  finally:
    print(msg)
    return mem_dic

#체크인 데이터 저장소에서 읽어오기
def readRemote():
  mem_dic = {}
  try:
    url = GIT_URL
    headers = {'Authorization': 'Bearer ' + GIT_AUTH}
    r = requests.get(url, headers=headers)
    content = r.json()['content']
    bytes2text = base64.b64decode(content).decode('utf-8')
    mem_dic = json.loads(bytes2text)
    msg = f"[readRemote]Total number of members: {len(mem_dic)}"
  except Exception as e:
    msg = f"[readRemote:E]Faild to read data from remote({e})"
  finally:
    print(msg)
    return mem_dic

#변경 사항이 있으면 저장하기
def updateData(mem_dic : dict, commitMsg:str):
  tem_dic = readLocal()
  if(mem_dic==tem_dic) :
    return "[updateData]There is no change to update"
  else :
    localMsg = saveLocal(mem_dic)
    remoteMsg = saveRemote(mem_dic, commitMsg)
    return "[updateData]\n"+localMsg+"\n"+remoteMsg

#체크인 데이터 로컬에 저장하기
def saveLocal(mem_dic : dict):
  try:
    with open(BACKUP_FILE, "wt", encoding="utf-8") as fp :
      json.dump(mem_dic, fp, indent=4, ensure_ascii=False)
    msg= f"[saveLocal]Saved Data of {len(mem_dic)} Members in local"
  except Exception as e:
    msg = f"[saveLocal:E]Faild to save data in local({e})"
  finally:
    print(msg)
    return msg

#체크인 데이터 저장소에 저장하기
def saveRemote(mem_dic : dict, commitMsg:str):
  try:
    url = GIT_URL
    headers = {'Authorization': 'Bearer ' + GIT_AUTH}
    content = base64.b64encode(json.dumps(mem_dic, indent=4, ensure_ascii=False).encode()).decode()
    r = requests.get(url, headers=headers)
    sha = r.json()['sha']
    now = getDate() + " " + getTime() +" | "+ str(len(mem_dic))
    r = requests.put(url, json={'message': f'Backup {BACKUP_FILE}({now}) :: {commitMsg}', 'sha': sha, 'content':content}, headers=headers)
    status = r.status_code
    if status == 200:
      msg= f"[saveRemote:{status}]Saved Data of {len(mem_dic)} Members"
    else :
      msg = f"[saveRemote:{status}]Faild to save data in remote"
  except Exception as e:
    msg = f"[saveRemote:E]Faild to save data in remote({e})"
  finally:
    print(msg)
    return msg

#등록 현황 문자열 반환
def getMember(mem_dic:dict) :
  sorted_list = sorted(mem_dic.values(),reverse=True, key= lambda x : int(x['checkIn_days']))
  strTmp = f"**----:scroll:{getDate()} 멤버 현황:scroll:----**\n"
  for i, mem in enumerate(sorted_list):
    if mem["checkIn_days"] == 0 :
      continue
    strTmp += f'{i+1:02d} | {abs(mem["checkIn_days"]):02d}일 차({mem["checkIn_date"]}) | {mem["medal"]}{mem["user_name"]}\n'
  return strTmp

#출결 현황 문자열 반환
def getToday(mem_dic:dict) :
  tmp_list =[]; newMem = 0 ; newMedal = 0
  for memdata in mem_dic.values() :
    if memdata['checkIn_date'] == getDate():
      tmp_list.append(memdata)
  sorted_list = sorted(tmp_list,key= lambda x : x['checkIn_time'])
  strTmp = f"**----:calendar_spiral:{getDate()} 출석 현황:calendar_spiral:----**"
  for i, mem in enumerate(sorted_list):
    day_num = mem["checkIn_days"]
    if day_num ==0 : 
      continue
    strTmp += f'\n{i+1:02d} | {mem["checkIn_time"]} | {mem["medal"]}{mem["user_name"]}({abs(day_num)}일 차)'
    if day_num == 1: 
      strTmp+= " :shamrock:"
      newMem+= 1
    if day_num ==10 or day_num==30 or day_num==66 :
      strTmp+= " :tada:"
      newMedal+=1
  return strTmp, len(sorted_list), newMem, newMedal