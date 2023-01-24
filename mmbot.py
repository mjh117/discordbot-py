import discord
from discord import app_commands
from discord.ext import commands
import datetime, json, re, os, requests, base64

TOKEN_TEST = os.environ['TOKEN_TEST']
TOKEN_MIMO = os.environ['TOKEN_MIMO']
GIT_AUTH = os.environ['GIT_AUTH']
GIT_URL = os.environ['GIT_URL']

intents = discord.Intents.default()
intents = discord.Intents.all()
#intents.members = True
#intents.message_content = True
backup_file = "mem_file.json"

bot = commands.Bot(command_prefix='!', intents=intents)
#체크인 데이터 읽어오기
with open(backup_file, "rt", encoding="utf-8") as fp:
  mem_dic = json.load(fp)
  print(f"Total number of members: {len(mem_dic)}")

@bot.event
async def on_ready():
  try:
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} command(s)")
  except Exception as e:
    print(e)

@bot.event
async def on_error(ctx):
  save(ctx)
  print("The bot has disconnected from the Discord server.")

@bot.tree.command(name="set")
@app_commands.describe(day_num="현재 누적 일수", date="마지막 체크인 날짜(yy-dd-mm 형식)", time ="마지막 체크인 시간(hh:mm 형식)")
async def setUser(interaction: discord.Interaction, day_num: int, date:str, time:str):
  #입력값 형식 체크
  if day_num < 0 : 
    await interaction.response.send_message(f"{day_num}(X) 양수 값을 입력해주세요.")
    return
  if not bool(re.match(r"^\d{2}-\d{2}-\d{2}$", date)) :
    await interaction.response.send_message(f"{date}(X) 날짜를 yy-dd-mm 형식으로 입력해주세요.")
    return
  if not bool(re.match(r"^\d{2}:\d{2}$", time)) :
    await interaction.response.send_message(f"{time}(X) 시간을 hh:mm 형식으로 입력해주세요.")
    return
  #체크인 설정값 저장 및 출력
  userId = str(interaction.user.id)
  userName = interaction.user.display_name
  medal = getMedal(day_num)
  if userName=='Key':
    medal = ':sparkles:'
    day_num = 1
  mem_dic[userId] = {"user_name" : userName, "checkIn_days": day_num, "checkIn_date": date, "checkIn_time":time, "medal" : medal}
  print("set data ::" , mem_dic[userId])
  await interaction.response.send_message(f"Setting Completed : {userName} `{time}` **{day_num}**일 차 ({date})")

@bot.tree.command(name="in")
@app_commands.describe(time="check-in 시간 입력")
async def checkIn(interaction: discord.Interaction, time: str = None):
  userId = str(interaction.user.id)
  userName = interaction.user.display_name
  #새 멤버 추가
  if userId not in mem_dic:
    mem_dic[userId] = {"user_name" : userName,"checkIn_days": 0, "checkIn_date":"00-00-00", "checkIn_time":"00-00", "medal" : ":third_place:"}
  #중복 출첵 막기
  date = getDate()
  if mem_dic[userId]["checkIn_date"] == date : 
    await interaction.response.send_message(f"{userName} 님, 출석 체크는 하루에 한 번만 가능합니다.")
    return
  #입력값 형식 체크
  if time == None: time = getTime()
  if not bool(re.match(r"^\d{2}:\d{2}$", time)) :
    await interaction.response.send_message(f"{time}(X) 시간을 hh:mm 형식으로 입력해주세요.")
    return
  #체크인 정보 저장 및 출력
  mem_dic[userId]["checkIn_days"] += 1
  mem_dic[userId]["checkIn_date"] = date
  mem_dic[userId]["checkIn_time"] = time
  day_num = mem_dic[userId]["checkIn_days"]
  #메달 지정 및 특정 유저 처리
  if(day_num==10 or day_num==30 or day_num==66) :
    mem_dic[userId]["medal"] = getMedal(day_num)
  if userName=='Key':
    mem_dic[userId]["medal"] = ':sparkles:'
    day_num = mem_dic[userId]["checkIn_days"] = 1
  medal = mem_dic[userId]["medal"]
  await interaction.response.send_message(f"{medal}{userName} in `{time}` {day_num}일 차 ({date})")

@bot.tree.command(name="out")
@app_commands.describe(time="check-out 시간 입력")
async def checkOut(interaction: discord.Interaction, time: str = None):
  userId = str(interaction.user.id)
  userName = interaction.user.display_name
  #오늘 체크인 데이터 없는 사람 거르기
  cur_date = getDate()
  if userId not in mem_dic or (userId in mem_dic and mem_dic[userId]["checkIn_date"]!=cur_date) :
    await interaction.response.send_message(f"{userName} 님, 먼저 체크인을 해주세요.")
    return
  #입력값 형식 체크
  if time == None: time = getTime()
  if not bool(re.match(r"^\d{2}:\d{2}$", time)) :
    await interaction.response.send_message(f"{time}(X) 시간을 hh:mm 형식으로 입력해주세요.")
    return
  #체류 시간 구하기
  checkIn_time = datetime.datetime.strptime(cur_date+" "+mem_dic[userId]["checkIn_time"], "%y-%m-%d %H:%M")
  checkOut_time = datetime.datetime.strptime(cur_date+" "+time, "%y-%m-%d %H:%M")
  if(checkIn_time>checkOut_time) : 
    await interaction.response.send_message(f"{time}(X) 체크인 이후의 시간을 입력해주세요.")
  stay_delta = checkOut_time-checkIn_time
  stay_time = str(datetime.timedelta(seconds=stay_delta.seconds))
  #체크아웃 정보 출력
  day_num = mem_dic[userId]["checkIn_days"]
  medal = mem_dic[userId]["medal"]
  await interaction.response.send_message(f"{medal}{userName} out `{time}` {day_num}일 차 ({stay_time[:-3]} 체류)")

@bot.command()
async def save(ctx):
  #로컬에 json 파일 백업
  with open(backup_file, "wt", encoding="utf-8") as fp :
    json.dump(mem_dic, fp, indent=4, ensure_ascii=False)
  #저장소에 json 파일 백업
  url = GIT_URL
  headers = {'Authorization': 'Bearer ' + GIT_AUTH}
  content = base64.b64encode(json.dumps(mem_dic, indent=4, ensure_ascii=False).encode()).decode()
  r = requests.get(url, headers=headers)
  sha = r.json()['sha']
  now = getDate() + " " + getTime()
  r = requests.put(url, json={'message': f'Backup {backup_file}({now})', 'sha': sha, 'content':content}, headers=headers)
  print("[save data]status :", r.status_code)
  await ctx.send(f"Saved Data of {len(mem_dic)} Members")

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

bot.run(TOKEN_TEST)