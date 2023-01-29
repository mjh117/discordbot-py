import discord
from discord import app_commands
from discord.ext import commands
import datetime, json, re, os, requests, base64
import traceback
from generalFunc import *

#로컬 환경변수 -> TEST 서버 토큰
#원격 환경변수 -> MIMO 서버 토큰
TOKEN_DICO = os.environ['TOKEN_DICO'] 

intents = discord.Intents.default()
intents = discord.Intents.all()
#intents.members = True
#intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

#저장소에서 데이터 읽어오기
mem_dic = readRemote()
saveLocal(mem_dic)

@bot.event
async def on_ready():
  try:
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} command(s)")
    print("Servers of which the bot is a member :: " + bot.guilds[0].name)
  except Exception as e:
    print(e)

@bot.event
async def on_disconnect():
  try:
    print(f"[on_disconnect][{getTime()}]")
    #변경 사항 저장
    resultMsg= updateData(mem_dic, "on_disconnect")
    print(resultMsg)
  except Exception as e:
    print(f"[on_disconnect][Exception][{getTime()}]",e)
    traceback.format_exc()

@bot.tree.command(name="set")
@app_commands.describe(day_num="현재 누적 일수", date="마지막 체크인 날짜(yy-mm-dd 형식 | ex.23-01-15)", time ="마지막 체크인 시간(hh:mm 형식 | ex.05:30)")
async def setUser(interaction: discord.Interaction, day_num: int, date:str, time:str):
  #일수 입력값 형식 체크
  if day_num < 0 : 
    return await interaction.response.send_message(f"{day_num}(X) 양수 값을 입력해주세요.")
  #날짜 입력값 형식 체크
  errDate = checkVal("date", date)
  if errDate :
    return await interaction.response.send_message(errDate)
  #시간 입력값 형식 체크
  errTime = checkVal("time", time)
  if errTime :
    return await interaction.response.send_message(errTime)
  #체크인 설정값 저장 및 출력
  userId = str(interaction.user.id)
  userName = interaction.user.display_name
  if userId=='941581845194240001':
    day_num = -1
  medal = getMedal(day_num)
  mem_dic[userId] = {"user_name" : userName, "checkIn_days": day_num, "checkIn_date": date, "checkIn_time":time, "medal" : medal}
  print("set data ::" , mem_dic[userId])
  await interaction.response.send_message(f"Setting Completed : {userName} `{time}` **{abs(day_num)}**일 차 ({date})")

@bot.tree.command(name="in")
@app_commands.describe(time="check-in 시간 입력(hh:mm 형식 | ex.05:30)")
async def checkIn(interaction: discord.Interaction, time: str = None):
  userId = str(interaction.user.id)
  userName = interaction.user.display_name
  isNewMem = userId not in mem_dic # True->NewMem, False->OldMem
  #새 멤버 추가
  if isNewMem:
    mem_dic[userId] = {"user_name" : userName,"checkIn_days": 0, "checkIn_date":"00-00-00", "checkIn_time":"00-00", "medal" : ""}
  #중복 출첵 막기
  date = getDate()
  if mem_dic[userId]["checkIn_date"] == date : 
    return await interaction.response.send_message(f"{userName} 님, 출석 체크는 하루에 한 번만 가능합니다.")
  #시간 자동 생성(해외 체크) or 수동 입력(형식 체크)
  if time == None:
    time = checkAbroad(mem_dic, userId)
  else :
    errTime = checkVal("time", time)
    if errTime :
      return await interaction.response.send_message(errTime)
  #체크인 정보 저장 및 출력
  mem_dic[userId]["checkIn_days"] += 1
  mem_dic[userId]["checkIn_date"] = date
  mem_dic[userId]["checkIn_time"] = time
  #특정 유저 처리
  if userId== '941581845194240001':
    mem_dic[userId]["checkIn_days"] = -1
  #새 멤버 메달 지정 및 상장 수여자 메달 변경
  day_num = mem_dic[userId]["checkIn_days"]
  celebrateStr=""
  if(isNewMem or day_num==10 or day_num==30 or day_num==66) :
    mem_dic[userId]["medal"] = getMedal(day_num)
    if isNewMem :
      celebrateStr=f"\n**|** *어서오세요! {userName} 님의 첫 시작을 응원합니다* :shamrock: **|**"
    else : 
      mentionStr = f"{discord.utils.get(interaction.guild.members, display_name='Key').mention}"
      celebrateStr = f"\n**|** *{day_num}일 차 상장러 대탄생! 축하합니다* :tada: **|**"+mentionStr
  #체크인 정보 출력
  medal = mem_dic[userId]["medal"]
  await interaction.response.send_message(f"{medal} {userName} in `{time}` {abs(day_num)}일 차 ({date}){celebrateStr}")

@bot.tree.command(name="out")
@app_commands.describe(time="check-out 시간 입력(hh:mm 형식 | ex.05:30)")
async def checkOut(interaction: discord.Interaction, time: str = None):
  userId = str(interaction.user.id)
  userName = interaction.user.display_name
  #오늘 체크인 데이터 없는 사람 거르기
  cur_date = getDate()
  if userId not in mem_dic or (userId in mem_dic and mem_dic[userId]["checkIn_date"]!=cur_date) :
    return await interaction.response.send_message(f"{userName} 님, 먼저 체크인을 해주세요.")
  #시간 자동 생성(해외 체크) or 수동 입력(형식 체크)
  if time == None:
    time = checkAbroad(mem_dic, userId)
  else :
    errTime = checkVal("time", time)
    if errTime :
      return await interaction.response.send_message(errTime)
  #체류 시간 구하기
  checkIn_time = datetime.datetime.strptime(cur_date+" "+mem_dic[userId]["checkIn_time"], "%y-%m-%d %H:%M")
  checkOut_time = datetime.datetime.strptime(cur_date+" "+time, "%y-%m-%d %H:%M")
  if(checkIn_time>checkOut_time) : 
    return await interaction.response.send_message(f"{time}(X) 체크인 이후의 시간을 입력해주세요.")
  stay_delta = checkOut_time-checkIn_time
  stay_time = str(datetime.timedelta(seconds=stay_delta.seconds))
  #체크아웃 정보 출력
  day_num = mem_dic[userId]["checkIn_days"]
  medal = mem_dic[userId]["medal"]
  await interaction.response.send_message(f"{medal} {userName} out `{time}` {abs(day_num)}일 차 ({stay_time[:-3]} 체류)")

####현황 체크 명령어
@bot.command()
async def member(ctx):
  sorted_list = sorted(mem_dic.values(),reverse=True, key= lambda x : int(x['checkIn_days']))
  strTmp = f"순위 | 누적 일수(마지막 출석일) | 이름\n\n**----:scroll:{getDate()} 멤버 현황:scroll:----**\n"
  for i, mem in enumerate(sorted_list):
    strTmp += f'{i+1:02d} | {abs(mem["checkIn_days"]):02d}일 차({mem["checkIn_date"]}) | {mem["medal"]}{mem["user_name"]}\n'
  await ctx.send(strTmp)

@bot.command()
async def today(ctx):
  tmp_list =[]
  for memdata in mem_dic.values() :
    if memdata['checkIn_date'] == getDate():
      tmp_list.append(memdata)
  sorted_list = sorted(tmp_list,key= lambda x : x['checkIn_time'])
  strTmp = f"순위 | 시간 | 이름(누적 일수)\n\n**----:calendar_spiral:{getDate()} 출석 현황:calendar_spiral:----**\n"
  for i, mem in enumerate(sorted_list):
    strTmp += f'{i+1:02d} | {mem["checkIn_time"]} | {mem["medal"]}{mem["user_name"]}({abs(mem["checkIn_days"])}일 차)\n'
  await ctx.send(strTmp)

####관리자 전용 명령어
@bot.command()
async def save(ctx, commitMsg:str=''):
  if "bot-manager" not in [r.name for r in ctx.author.roles]:
    return await ctx.send("You do not have permission to use this command.")
  #변경 사항 저장
  resultMsg= updateData(mem_dic, commitMsg)
  await ctx.send(resultMsg)

@bot.command()
async def viewMemData(ctx, userId:str):
  if "bot-manager" not in [r.name for r in ctx.author.roles]:
    return await ctx.send("You do not have permission to use this command.")
  await ctx.send(f"View Member data of {userId}:\n{mem_dic[userId]}")

@bot.command()
async def setMemData(ctx, userId:str, key:str, val:str, valType:int= 0):
  if "bot-manager" not in [r.name for r in ctx.author.roles]:
    return await ctx.send("You do not have permission to use this command.")
  #valType이 1이면 value가 int 타입(default 값 str타입)
  if valType == 1 : val = int(val)
  mem_dic[userId][key] = val
  await ctx.send(f"Set Member data '{key} : {val}':\n{mem_dic[userId]}")

@bot.command()
async def delMemData(ctx, userId:str):
  if "bot-manager" not in [r.name for r in ctx.author.roles]:
    return await ctx.send("You do not have permission to use this command.")
  if userId=="ALL_MEM":
    mem_dic.clear()
    return await ctx.send(f"All Members data Deleted(Current Members: {len(mem_dic)})")
  else :
    del mem_dic[userId]
    return await ctx.send(f"{userId} Member data Deleted(Current Members: {len(mem_dic)})")

bot.run(TOKEN_DICO)