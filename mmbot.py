import discord
from discord import app_commands
from discord.ext import commands
import datetime, json, re, os, requests, base64
from generalFunc import *

TOKEN_TEST = os.environ['TOKEN_TEST']
TOKEN_MIMO = os.environ['TOKEN_MIMO']

intents = discord.Intents.default()
intents = discord.Intents.all()
#intents.members = True
#intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

#체크인 데이터 읽어오기
backup_file = "mem_file.json"
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
async def on_disconnect():
  msg = saveRemote()
  print("[on_disconnect]", msg)
  print("The bot has disconnected from the Discord server.")

@bot.tree.command(name="set")
@app_commands.describe(day_num="현재 누적 일수", date="마지막 체크인 날짜(yy-dd-mm 형식)", time ="마지막 체크인 시간(hh:mm 형식)")
async def setUser(interaction: discord.Interaction, day_num: int, date:str, time:str):
  #일수, 날짜, 시간 입력값 형식 체크
  if day_num < 0 : 
    return await interaction.response.send_message(f"{day_num}(X) 양수 값을 입력해주세요.")
  msg_date = checkVal("date", date)
  if msg_date :
    return await interaction.response.send_message(msg_date)
  msg_time = checkVal("time", time)
  if msg_time :
    return await interaction.response.send_message(msg_time)
  #체크인 설정값 저장 및 출력
  userId = str(interaction.user.id)
  userName = interaction.user.display_name
  medal = getMedal(day_num)
  if userId=='941581845194240001':
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
    return await interaction.response.send_message(f"{userName} 님, 출석 체크는 하루에 한 번만 가능합니다.")
  #시간 입력값 형식 체크
  if time == None: time = getTime()
  msg_time = checkVal("time", time)
  if msg_time : 
    return await interaction.response.send_message(msg_time)
  #체크인 정보 저장 및 출력
  mem_dic[userId]["checkIn_days"] += 1
  mem_dic[userId]["checkIn_date"] = date
  mem_dic[userId]["checkIn_time"] = time
  day_num = mem_dic[userId]["checkIn_days"]
  #메달 지정 및 특정 유저 처리
  mentionStr=""
  if(day_num==10 or day_num==30 or day_num==66) :
    mem_dic[userId]["medal"] = getMedal(day_num)
    mentionStr=f"{discord.utils.get(interaction.guild.members, display_name='Key').mention}"
  if userId=='941581845194240001':
    mem_dic[userId]["medal"] = ':sparkles:'
    day_num = mem_dic[userId]["checkIn_days"] = 1
  medal = mem_dic[userId]["medal"]
  await interaction.response.send_message(f"{medal}{userName} in `{time}` {day_num}일 차 ({date}) {mentionStr}")

@bot.tree.command(name="out")
@app_commands.describe(time="check-out 시간 입력")
async def checkOut(interaction: discord.Interaction, time: str = None):
  userId = str(interaction.user.id)
  userName = interaction.user.display_name
  #오늘 체크인 데이터 없는 사람 거르기
  cur_date = getDate()
  if userId not in mem_dic or (userId in mem_dic and mem_dic[userId]["checkIn_date"]!=cur_date) :
    return await interaction.response.send_message(f"{userName} 님, 먼저 체크인을 해주세요.")
  #시간 입력값 형식 체크
  if time == None: time = getTime()
  msg_time = checkVal("time", time)
  if msg_time :
    return await interaction.response.send_message(msg_time)
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


####봇관리자 전용 명령
@bot.command()
async def save(ctx):
  if "bot-manager" not in [r.name for r in ctx.author.roles]:
    return await ctx.send("You do not have permission to use this command.")
  #로컬에 json 파일 백업
  with open(backup_file, "wt", encoding="utf-8") as fp :
    json.dump(mem_dic, fp, indent=4, ensure_ascii=False)
  #저장소에 json 파일 백업
  await ctx.send(saveRemote(mem_dic))

@bot.command()
async def member(ctx):
  sorted_list = sorted(mem_dic.values(),reverse=True, key= lambda x : int(x['checkIn_days']))
  strTmp = "순위 | 누적 일수(마지막 출석일) | 이름\n"
  for i, mem in enumerate(sorted_list):
    strTmp += f'{i+1:02d} | {mem["checkIn_days"]}일 차({mem["checkIn_date"]}) | {mem["medal"]}{mem["user_name"]}\n'
  await ctx.send(strTmp)

@bot.command()
async def today(ctx):
  tmp_list =[]
  for memdata in mem_dic.values() :
    if memdata['checkIn_date'] == getDate():
      tmp_list.append(memdata)
  sorted_list = sorted(tmp_list,key= lambda x : x['checkIn_time'])
  strTmp = "순위 | 시간 | 이름(누적 일수)\n"
  for i, mem in enumerate(sorted_list):
    strTmp += f'{i+1:02d} | {mem["checkIn_time"]} | {mem["medal"]}{mem["user_name"]}({mem["checkIn_days"]}일 차)\n'
  await ctx.send(strTmp)

@bot.command()
async def reset(ctx):
  if "bot-manager" not in [r.name for r in ctx.author.roles]:
    return await ctx.send("You do not have permission to use this command.")
  mem_dic.clear()
  await ctx.send(f"Reset Completed : {mem_dic}")

bot.run(TOKEN_TEST)