import discord
from discord import app_commands
from discord.ext import commands, tasks
import datetime, json, re, os, requests, base64
import traceback
from generalFunc import *

#로컬 환경변수 -> TEST 서버 토큰
#원격 환경변수 -> MIMO 서버 토큰
TOKEN_DICO = os.environ['TOKEN_DICO']
REPORT_CHANNEL_ID = os.environ['REPORT_CHANNEL_ID']

intents = discord.Intents.default()
intents = discord.Intents.all()
#intents.members = True
#intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

#저장소에서 데이터 읽어오기
mem_dic = readRemote()
saveLocal(mem_dic)

###백그라운드 태스크
@tasks.loop(hours=3)
async def backupData():
  resultMsg= updateData(mem_dic, "(loop)backupData")
  print(f"[backupData][{getTime()}]{resultMsg}")

@tasks.loop(time=datetime.time(hour=18, minute=0, tzinfo= datetime.timezone(datetime.timedelta(hours=9))))
async def dailyReport():
  message_channel = bot.get_channel(int(REPORT_CHANNEL_ID))
  print(f"Got channel {message_channel}")
  memberStr = getMember(mem_dic)
  todayStr, todayMem, newMem, newMedal = getToday(mem_dic)
  reportStr = "Hello, I'm MMBot!\n"
  reportStr+= "> \n**----:robot:Today's Daily Report:robot:----**\n"
  reportStr+= f"등록 멤버({len(mem_dic):02d}) | 출석 멤버({todayMem:02d})\n"
  reportStr+= f"신규 멤버({newMem:02d}) | 승급 멤버({newMedal:02d})"
  await message_channel.send(reportStr)
  await message_channel.send("> \n"+memberStr)
  await message_channel.send("> \n"+todayStr)

@backupData.before_loop
@dailyReport.before_loop
async def before():
  await bot.wait_until_ready()
  print("Finished waiting")

### 봇 올라오거나 연결 끊길 때
@bot.event
async def on_ready():
  try:
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} command(s)")
    print("Servers of which the bot is a member :: " + bot.guilds[0].name)
    dailyReport.start()
    backupData.start()
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

@bot.event
async def on_close():
  print(f"[on_close][Exception][{getTime()}]")

@bot.event
async def on_error():
  print(f"[on_error][Exception][{getTime()}]")

####데이터 설정 명령어
@bot.tree.command(name="utc")
@app_commands.describe(utc_hour="거주 지역의 UTC offset값을 정수로 입력해주세요(ex. 독일: 1, 뉴욕: -5)")
async def setUtcHour(interaction: discord.Interaction, utc_hour: int):
  userId = str(interaction.user.id)
  userName = interaction.user.display_name
  #미등록 멤버 제한
  if userId not in mem_dic : 
    return await interaction.response.send_message(f"{userName} 님, 먼저 멤버 등록을 해주세요. 채팅창에 `!new`를 입력해보세요.")
  #정수 입력값 형식 체크
  if not (utc_hour >= -12 and utc_hour <= 14): # -12 ~ +14 범위의 값
    return await interaction.response.send_message(f"{utc_hour}(X) -12 ~ 14 범위의 값을 입력해주세요.")
  #utc_hour값 추가
  mem_dic[userId]["utc_hour"]= utc_hour
  #utc 시간대 출력
  utcStr = f"UTC+{utc_hour}:00" if utc_hour>=0 else f"UTC{utc_hour}:00"
  await interaction.response.send_message(f"TimeZone Setting Completed :{utcStr}")
  print("[setUtcHour]", userName, utcStr)

@bot.tree.command(name="limit")
@app_commands.describe(time_limit ="체크인 제한 시간(hh:mm 형식 | ex.05:30)")
async def setTimeLimit(interaction: discord.Interaction, time_limit:str):
  userId = str(interaction.user.id)
  userName = interaction.user.display_name
  #미등록 멤버 제한
  if userId not in mem_dic : 
    return await interaction.response.send_message(f"{userName} 님, 먼저 멤버 등록을 해주세요. 채팅창에 `!new`를 입력해보세요.")
  #시간 입력값 형식 체크
  errTime = checkVal("time", time_limit)
  if errTime :
    return await interaction.response.send_message(errTime)
  mem_dic[userId]["time_limit"] = time_limit
  await interaction.response.send_message(f"TimeLimit Setting Completed : {time_limit}")
  print("[setTimeLimit]", mem_dic[userId]["time_limit"])

@bot.tree.command(name="set")
@app_commands.describe(day_num="현재 누적 일수", date="마지막 체크인 날짜(yy-mm-dd 형식 | ex.23-01-15)", time ="마지막 체크인 시간(hh:mm 형식 | ex.05:30)")
async def setUser(interaction: discord.Interaction, day_num: int, date:str, time:str):
  userId = str(interaction.user.id)
  userName = interaction.user.display_name
  #미등록 멤버 제한
  if userId not in mem_dic :
    return await interaction.response.send_message(f"{userName} 님, 먼저 멤버 등록을 해주세요. 채팅창에 `!new`를 입력해보세요.")
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
  if userId=='941581845194240001':
    day_num = -1
  medal = getMedal(day_num)
  #utc_hour 지워지지 않도록 변경된 값만 수정
  mem_dic[userId]["checkIn_days"]= day_num
  mem_dic[userId]["checkIn_date"]= date
  mem_dic[userId]["checkIn_time"]=time
  mem_dic[userId]["medal"] = medal
  await interaction.response.send_message(f"Setting Completed : {userName} `{time}` **{abs(day_num)}**일 차 ({date})")
  print("[setUser]", mem_dic[userId])

####출석 체크 명령어
@bot.tree.command(name="in")
@app_commands.describe(time="check-in 시간 입력(hh:mm 형식 | ex.05:30)")
async def checkIn(interaction: discord.Interaction, time: str = None):
  userId = str(interaction.user.id)
  userName = interaction.user.display_name
  #미등록 멤버 제한
  if userId not in mem_dic :
    return await interaction.response.send_message(f"{userName} 님, 먼저 멤버 등록을 해주세요. 채팅창에 `!new`를 입력해보세요.")
  #중복 출첵 막기
  cur_date = getDate()
  if mem_dic[userId]["checkIn_date"] == cur_date : 
    return await interaction.response.send_message(f"{userName} 님, 출석 체크는 하루에 한 번만 가능합니다.")
  #시간 자동 생성(해외 체크) or 수동 입력(형식 체크)
  if time == None:
    time = checkAbroad(mem_dic, userId)
  else :
    errTime = checkVal("time", time)
    if errTime : return await interaction.response.send_message(errTime)
  #목표 시간 비교하기
  if "time_limit" in mem_dic[userId] :
    cur_time = datetime.datetime.strptime(cur_date+" "+time, "%y-%m-%d %H:%M")
    time_limit = datetime.datetime.strptime(cur_date+" "+mem_dic[userId]["time_limit"], "%y-%m-%d %H:%M")
    if(cur_time>time_limit) : 
      return await interaction.response.send_message(f"{time}(X) 목표한 체크인 시간은 {mem_dic[userId]['time_limit']}입니다.")
  #체크인 정보 저장 및 출력
  mem_dic[userId]["checkIn_days"] += 1
  mem_dic[userId]["checkIn_date"] = cur_date
  mem_dic[userId]["checkIn_time"] = time
  #특정 유저 처리
  if userId== '941581845194240001':
    mem_dic[userId]["checkIn_days"] = -1
  #새 멤버 메달 지정 및 승급 메달 변경
  day_num = mem_dic[userId]["checkIn_days"]
  celebrateStr=""
  if(day_num==1 or day_num==10 or day_num==30 or day_num==66) :
    mem_dic[userId]["medal"] = getMedal(day_num)
    if day_num==1 :
      celebrateStr=f"\n**|** *어서오세요! {userName} 님의 첫 시작을 응원합니다* :shamrock: **|**"
    else : 
      #mentionStr = f"{discord.utils.get(interaction.guild.members, display_name='Key').mention}"
      celebrateStr = f"\n**|** *{day_num}일 차 승급러 대탄생! 축하합니다* :tada: **|**"#+mentionStr
      #celebrateStr += "\n**|** *영문 이름&이미지를 답장으로 달아주세요* :blush: **|**"
  #체크인 정보 출력
  medal = mem_dic[userId]["medal"]
  await interaction.response.send_message(f"{medal} {userName} in `{time}` {abs(day_num)}일 차 ({cur_date}){celebrateStr}")
  print("[checkIn]", userName, time)

@bot.tree.command(name="out")
@app_commands.describe(time="check-out 시간 입력(hh:mm 형식 | ex.05:30)")
async def checkOut(interaction: discord.Interaction, time: str = None):
  userId = str(interaction.user.id)
  userName = interaction.user.display_name
  #미등록 멤버 제한
  if userId not in mem_dic :
    return await interaction.response.send_message(f"{userName} 님, 먼저 멤버 등록을 해주세요. 채팅창에 `!new`를 입력해보세요.")
  #오늘 체크인 데이터 없는 사람 거르기
  cur_date = getDate()
  if mem_dic[userId]["checkIn_date"]!=cur_date :
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
  await interaction.response.send_message(f"{medal} {userName} out `{time}` {abs(day_num)}일 차 ({cur_date} | {stay_time[:-3]} 체류)")

####현황 체크 명령어
@bot.command()
async def member(ctx):
  memberStr = getMember(mem_dic)
  await ctx.send("순위 | 누적일(마지막 출석일) | 이름\n\n"+memberStr)

@bot.command()
async def today(ctx):
  todayStr = getToday(mem_dic)[0]
  await ctx.send("순위 | 시간 | 이름(누적일)\n\n"+todayStr)

####멤버 등록 명령어
@bot.command()
async def new(ctx):
  userId = str(ctx.author.id)
  userName = ctx.author.display_name
  if userId not in mem_dic : 
    mem_dic[userId] = {"user_name" : userName,"checkIn_days": 0, "checkIn_date":"00-00-00", "checkIn_time":"00-00", "medal" : ""}
    return await ctx.send(f"{userName} 님, 멤버 등록이 완료되었습니다. 환영합니다! :blush:")
  else :
    return await ctx.send(f"{userName} 님은 이미 등록된 멤버입니다.")

####관리자 전용 명령어
@bot.command()
async def save(ctx, commitMsg:str=''):
  if "bot-manager" not in [r.name for r in ctx.author.roles]:
    return await ctx.send("You do not have permission to use this command.")
  #변경 사항 저장
  resultMsg= updateData(mem_dic, commitMsg)
  await ctx.send(resultMsg)

@bot.command()
async def dReport(ctx):
  await dailyReport()

@bot.command()
async def viewMemData(ctx, userId:str):
  if "bot-manager" not in [r.name for r in ctx.author.roles]:
    return await ctx.send("You do not have permission to use this command.")
  if userId not in mem_dic :
    return await ctx.send("KeyError: "+userId)
  await ctx.send(f"View Member data of {userId}:\n{mem_dic[userId]}")

@bot.command()
async def setMemData(ctx, userId:str, key:str, val:str, valType:int= 0):
  if "bot-manager" not in [r.name for r in ctx.author.roles]:
    return await ctx.send("You do not have permission to use this command.")
  if userId not in mem_dic :
    return await ctx.send("KeyError: "+userId)  
  #valType이 1이면 value가 int 타입(default 값 str타입)
  if valType == 1 : val = int(val)
  mem_dic[userId][key] = val
  await ctx.send(f"Set Member data '{key} : {val}':\n{mem_dic[userId]}")

@bot.command()
async def delMemData(ctx, userId:str, key:str=None):
  if "bot-manager" not in [r.name for r in ctx.author.roles]:
    return await ctx.send("You do not have permission to use this command.")
  #전체 멤버 삭제
  if userId=="ALL_MEMBER_DATA":
    mem_dic.clear()
    return await ctx.send(f"All Members data Deleted(Current Members: {len(mem_dic)})")
  #멤버 한 명 삭제
  if userId not in mem_dic :
    return await ctx.send("KeyError: "+userId)
  if key is None :
    del mem_dic[userId]
    return await ctx.send(f"All data of {userId} Deleted(Current Members: {len(mem_dic)})")
  #멤버 정보 한 개 삭제
  if key not in mem_dic[userId] :
    return await ctx.send("KeyError: "+key)
  del mem_dic[userId][key]
  return await ctx.send(f"'{key}' data of {userId} Deleted\n{mem_dic[userId]}")
try:
  bot.run(TOKEN_DICO)
except Exception as e:
  print(f"[RuntimeError][{getTime()}]",e)
  traceback.format_exc()