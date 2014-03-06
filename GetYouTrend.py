# -*- coding: utf-8 -*-
import sys
import traceback
import tweepy
import MeCab
import unicodedata
import glob
import math
import re
import datetime
import time
import random
import MySQLdb

dict1 = {
'consumer_key' : "***************" ,
'consumer_secret' : "***************",
'access_token_key' : "***************",
'access_token_secret' : "***************"
}
auth = tweepy.OAuthHandler(dict1['consumer_key'], dict1['consumer_secret'])
auth.set_access_token(dict1['access_token_key'], dict1['access_token_secret'])
api = tweepy.API(auth)
i = 0
iDF = {}
oldTime = datetime.datetime.now().hour
postList = ["このツイートをリツイートすると、あなたのトレンドを解析します！鍵垢の人は http://getyoutrend.dip.jp にアクセスしてアプリの許可をして下さい",
					"時々、エラーになります。ご了承くださいm(__)m",
					"あなたのトレンドを解析したい場合は、このツイートをリツイートして下さい！！鍵垢の人は http://getyoutrend.dip.jp にアクセスしてアプリの許可をして下さい",
					"このツイートをリツイートで解析！鍵垢の人は http://getyoutrend.dip.jp にアクセスしてアプリの許可をして下さい",
					"動きが遅いのも、バクではなく仕様です。( ｰ`дｰ´)ｷﾘｯ",
					"このツイートをリツイート→あなたのトレンドを解析！！鍵垢の人は http://getyoutrend.dip.jp にアクセスしてアプリの許可をして下さい",
					"精度と速度は、改善していきます(多分)",
					"このツイートをリツイートするといいことあるよ（嘘）鍵垢の人は http://getyoutrend.dip.jp にアクセスしてアプリの許可をして下さい",
					"アカウント凍結されるのは、バグではなくTwitterの仕様です。"]

#####################
##データベースに接続##
####################
def connectDB():
	connector = MySQLdb.connect(host="localhost", db="***************", user="***************", passwd="***************", charset="utf8")
	cursor = connector.cursor()
	db_list = [connector,cursor]
	return db_list

####################
###ユーザAPIの設定###
####################
def userApi(userId):
	db_list = connectDB()
	connector = db_list[0]
	cursor = db_list[1]
	try:
		sql = "select * from oauth_token where id = " + str(userId) + ";"
		cursor.execute(sql)
		result = cursor.fetchall()
		auth = tweepy.OAuthHandler("***************", "***************")
		print result
		auth.set_access_token(result[0][1], result[0][2])
		print "set OK!!"
	finally:
		cursor.close()
		connector.close()
	return tweepy.API(auth)


#############
##Tweetを取得##
#############
def getTweet(scrName,usrID,protect=False):
	print "Get tweet..."
	global api
	if protect:
		print "protect!"
		newApi = userApi(usrID)
		tweets = []
		tweets.append(newApi.user_timeline(scrName,count=200,page=1))
		tweets.append(newApi.user_timeline(scrName,count=100,page=2))
	else:
		tweets = []
		tweets.append(api.user_timeline(scrName,count=200,page=1))
		tweets.append(api.user_timeline(scrName,count=100,page=2))
	print "tweet Geted!"
	twFile = ""
	for tweet in tweets:
		for tweet_txt in tweet:
			txt = tweet_txt.text
			if "RT " not in txt: #RTは含まない
				if "@" in txt: #@ユーザ名 のあるツイートは「@ユーザ名」を切り取る
					txt = mentionCut(txt)
				if "http" not in txt: #URLが名詞にヒットするので、切り取っておく。
					twFile += txt + "\n"
	return twFile

##################
##宛先ユーザのを消す##
##################
def mentionCut(txt1):
	twtxt = txt1
	temp = re.split("@+\w+",twtxt)
	twtxt = ""
	for tmp in temp:
		twtxt += tmp
	return twtxt

###################################
##URLが名詞にヒットするので、切り取っておく##
###################################
def urlCut(txt1):
	twtxt = txt1
	#tmp = re.split("http+.*/+",twtxt)←だと
	 #「なう http://www.twitter.com/ なう2 https://www2.twitter.com/」
	#の場合 「なう２」も切り取られる
	tmp = twtxt.split(".")
	twtxt = ""
	for txtTemp in tmp:
		twtxt += txtTemp
	#「なう http://wwwtwittercom/ なう２ https://www2twittercom/」になる
	tmp = twtxt.split("/")
	twtxt = ""
	for txtTemp in tmp:
		twtxt += txtTemp
	#「なう http:wwwtwittercom なう２ https:www2twittercom」になる
	tmp =twtxt.split(":")
	twtxt = ""
	for txtTemp in tmp:
		twtxt += txtTemp
	#「なう httpwwwtwittercom なう２ httpswww2twittercom」になる
	tmp = re.split("http+\w+",twtxt)
	twtxt = ""
	for txtTemp in tmp:
		twtxt += txtTemp
	return twtxt
	
#############
##タグを抽出##
#############
def splitTag(txt):
	tmp = re.split(u' |　|\n',txt)
	txt = ''
	tag = []
	for t in tmp:
		if len(t) == 0:
			pass
		elif u'#' == t[0]:
			tag.append(t)
		else:
			txt += t + ' '
	#print 'tweet = ',txt
	#print 'tag =',tag
	rt_list = [txt,tag]
	return rt_list #ツイートとタグを返す

################
###名詞を抽出###
################
def extractKeyword(text,word_class=["名詞","形容詞"]):
	tmp = splitTag(text) #まずハッシュタグを抽出
	text = tmp[0]
	keywords = tmp[1]
	tagger = MeCab.Tagger('-Ochasen')
	node = tagger.parseToNode(text.encode('utf-8'))
	while node:
		try:
			if node.feature.split(',')[0] in word_class:
			#print node.surface
				uniname = node.surface.decode('utf-8')[0] #名詞の一文字目 ↓で数字、ひらがな、カタカナ、漢字、アルファベットのみをkeywordsに追加
				if (unicodedata.name(uniname)[0:8] == "HIRAGANA") or (unicodedata.name(uniname)[0:8] == "KATAKANA") or (unicodedata.name(uniname)[0:18] == "HALFWIDTH KATAKANA") or (unicodedata.name(uniname)[0:3] == "CJK") or (unicodedata.name(uniname)[0:5] == "LATIN") or (unicodedata.name(uniname)[0:5] == "DIGIT"):
					term = node.surface.replace('*','＊')
					term = term.replace('"','”')
					term = term.replace("'","’")
					keywords.append(term.decode('utf-8'))
					#print node.surface.decode('utf-8')
		except Exception as e:
			print "-"*10
			print "エラー(MeCab)"
			print node.surface
			print str(type(e))
			print str(e.args)
			print e.message
			print str(e)
			print "-"*10
		node = node.next
	return keywords

##################
#####tfを算出#####
##################
def get_tf(doc_keywords):
	TF = {}
	doc_keywords_num = len(doc_keywords)
	for doc_keyword in doc_keywords:
		if doc_keyword not in TF.keys():
			TF.update({doc_keyword : 1.0/doc_keywords_num})
		else:
			TF[doc_keyword] += 1.0/doc_keywords_num
	return TF


#################
####idfを算出####
#################
def get_idf2(tokens):
	db_list = connectDB()
	connector = db_list[0]
	cursor = db_list[1]
	idf = {}
	sql = "select * from tweet_num;"
	cursor.execute(sql)
	result = cursor.fetchall()
	twNum = result[0][0]
	print "get_idf2..."	
	for term in tokens:
		#debug用
		#print term
		term = term.encode('utf-8')
		term = term.replace('*','＊')
		term = term.replace('"','”')
		term = term.replace("'","’")

		try: #term = "*" だとエラーが出るからtryにしとく
			sql = "select num from term_num where term like '" + term + "';"
			cursor.execute(sql)
			result = cursor.fetchall()
			if len(result) == 0:
				#DBになくても同じユーザのツイートが何度も追加されたくないので追加処理はしない
				try:
					idf.update({term.decode('utf-8'):math.log(float(twNum))})
				except:
					print "\n(a)error"
					print "term =",term
					print "idf =",float(twNum)
					print
					pass
			else:
				#DBにあるので単語を取得
				try:
					db_num = result[0][0]
					idf.update({term.decode('utf-8'):math.log(float(twNum)/(db_num+1.0))})
				except:
					print "\n(b)error"
					print "term =",term
					print "idf =",float(twNum)/(db_num+1.0)
					print
					pass
		except Exception as e:
			print "エラー(idf2)"
			print str(type(e))
			print str(e.args)
			print e.message
			print str(e)
	print type(term)
	print "get_idf2 fin..."
	cursor.close()
	connector.close()
	return idf

def getTrend(scrName,usrID,protect):
	global api
	global iDF
	print "getTrend..."
	word_class = ["名詞","形容詞"]
	twFile = getTweet(scrName,usrID,protect)
	print "geted tweet"
	#print twFile
	keywords = extractKeyword(twFile , word_class)
	print "geted keywords"
	tokens = set(keywords)
	print "geted token"
	iDF = get_idf2(tokens)
	#print iDF
	TF_iDF = {}
	#print keywordDict[str(num)]
	TF = get_tf(keywords)
	print "get tf..."
	for doc_token in tokens:
		try:
			TF_iDF.update({doc_token : TF[doc_token] * iDF[doc_token]})
		except:
			print "エラーやわ"
			print "key =",doc_token
			print "tf =",TF[doc_token]
			print "idf =",iDF[doc_token]
			pass
	mentionTweet = "@" + scrName + " のトレンドは"
	rank = 0
	key_tmp = [] #特徴単語の小文字を格納
	for key, value in sorted(TF_iDF.items(), key=lambda x:x[1], reverse=True):
		key = key.encode('utf-8')
		#print type(mentionTweet),type(key)
		if (key.lower() not in key_tmp)and(len(key.decode('utf-8')) > 2): #大文字小文字を区別せずに同じ単語があれば特徴単語としない.2文字は特徴としない
			if len(mentionTweet.decode('utf-8') + key.decode('utf-8'))>=136:
				break
			key_tmp.append(key.lower())
			rank += 1
			if rank < 6:
				mentionTweet += "\n"
				mentionTweet += str(rank)+"位「"+key+"」"
			else:
				break #ここにその他は、、、を追加
			#if rank == 8:
			#	break
	print mentionTweet
	postMention(mentionTweet)
	api.create_friendship(usrID)

################
##特徴単語をTweet##
################
def postMention(postmsg):
	global api
	global postList
	global i
	global oldTime
	api.update_status(postmsg)
	#try:
	if oldTime != datetime.datetime.now().hour:
		oldTime = datetime.datetime.now().hour
		postmsg = postList[i]
		time.sleep(2) #2秒待ってからツイート
		api.update_status(postmsg)
		if i == len(postList):
			i = 0
		i += 1

class AbstractedlyListener(tweepy.StreamListener):
	""" Let's stare abstractedly at the User Streams ! """
	def on_status(self, status):
		try:
			print status.text
		except:
			print status.text.encode('utf-8')
			pass
		print status.author.screen_name
		request = "RT @GetYouTrend2:"
		global api
		followersList = []
		#print type(status.text.encode('utf-8'))
		statusText = status.text.encode('utf-8')
		matchFlag =  re.match("@GetYouTrend2 \[.+\]at:.+$",statusText)
		if request in statusText:
			print "req1通過"
			if "このツイートをリツイート" in statusText:
				#print "RT"
				#followers = api.followers()
				#for follower in followers:
				#	followersList.append(follower.screen_name)
				#if status.author.screen_name in followersList:
				print "解析開始",datetime.datetime.now()
				#try:
				getTrend(status.author.screen_name,status.author.id,status.author.protected)
		elif matchFlag != None:
			tmp = re.split('@GetYouTrend2 \[',statusText)
			tmp1 = re.split('\]at:',tmp[1])
			postmsg = '@' + tmp1[1] + ' ' + tmp1[0] + '（これはbotです）'
			print postmsg
			if len(postmsg.decode('utf-8')) <= 140:
				print postmsg
				api.update_status(postmsg)
			else:
				print '140字を超えてます。'
				postmsg = '@' + status.author.screen_name + '140字を超えています。'
				if len(postmsg.decode('utf-8')) <= 140:
					api.update_status(postmsg)
				else:
					print 'エラー'

def main():
	print "FistPost"
	firstpost = postList[random.randint(0, len(postList)-1)]
	try:
		api.update_status(firstpost)
	except:
		print firstpost
		print 
		print "post error"
		pass
	print "stream"
	stream = tweepy.Stream(auth, AbstractedlyListener(), secure=True)
	for cnt in range(100):
		try:
			stream.userstream()
		except:
		    # エラーの情報をsysモジュールから取得
		    info = sys.exc_info()
		    # tracebackモジュールのformat_tbメソッドで特定の書式に変換
		    tbinfo = traceback.format_tb( info[2] )
		 
		    # 収集した情報を読みやすいように整形して出力する----------------------------
		    print 'Python Error.'.ljust( 80, '=' )
		    for tbi in tbinfo:
		        print tbi
		    print '  %s' % str( info[1] )
		    print '\n'.rjust( 80, '=' )
		    pass
		    
if __name__=="__main__":
	main()
