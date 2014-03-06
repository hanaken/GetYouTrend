# -*- coding: utf-8 -*-
import sys
import traceback
import tweepy
import re
import codecs
import datetime
import MeCab
import unicodedata
import math
import MySQLdb
import time

twNum = 0
txt = ''
twDict = {}
Q = sys.argv[1:]
dict1 = {
'consumer_key' : "***************" ,
'consumer_secret' : "***************",
'access_token_key' : "***************",
'access_token_secret' : "***************"
}
auth = tweepy.OAuthHandler(dict1['consumer_key'], dict1['consumer_secret'])
auth.set_access_token(dict1['access_token_key'], dict1['access_token_secret'])
api = tweepy.API(auth)

#####################
##データベースに接続##
####################
def connectDB():
	connector = MySQLdb.connect(host="localhost", db="***************", user="***************", passwd="***************", charset="utf8")
	cursor = connector.cursor()
	db_list = [connector,cursor]
	return db_list

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
		elif '#' == t[0]:
			tag.append(t)
		else:
			txt += t + u' '
	#print 'tweet = ',txt
	#print 'tag =',tag
	rt_list = [txt,tag]
	return rt_list #ツイートとタグを返す

################
###名詞を抽出###
################
def extractKeyword(text,word_class=["名詞","形容詞"]):
	tmp = splitTag(text.decode('utf-8')) #まずハッシュタグを抽出
	text = tmp[0]
	keywords = tmp[1]
	tagger = MeCab.Tagger('-Ochasen')
	node = tagger.parseToNode(text.encode('utf-8'))
	while node:
		try:
			if node.feature.split(',')[0] in word_class:
				#print node.surface.decode("utf-8")
				uniname = node.surface.decode("utf-8")[0] #名詞の一文字目 ↓で数字、ひらがな、カタカナ、漢字、アルファベットのみをkeywordsに追加
				if (unicodedata.name(uniname)[0:8] == u"HIRAGANA") or (unicodedata.name(uniname)[0:8] == u"KATAKANA") or (unicodedata.name(uniname)[0:18] == u"HALFWIDTH KATAKANA") or (unicodedata.name(uniname)[0:3].decode("utf-8") == u"CJK") or (unicodedata.name(uniname)[0:5].decode("utf-8") == u"LATIN") or (unicodedata.name(uniname)[0:5].decode("utf-8") == u"DIGIT"):
					if (node.surface.decode("utf-8") not in keywords)and(len(node.surface.decode("utf-8")) > 1): #idf用なので辞書にあれば格納しない。1文字も格納しない。
						keywords.append(node.surface.decode("utf-8"))
		except:
			pass
		node = node.next
	return keywords

def getKeyword(txt):
	keywords = extractKeyword(txt,["名詞","形容詞"])
	keywords = set(keywords) #被りなしにする
	print "Get Keyword"
	db_list = connectDB()
	connector = db_list[0]
	cursor = db_list[1]
	try:
		for key in keywords:
			if len(key)==1: #1文字は格納しない。
				continue
			key = key.encode("utf-8")
			key = MySQLdb.escape_string(key);
			key = key.replace('*','＊')
			key = key.replace('"','”')
			key = key.replace("'","’")
			sql = "select num from term_num where term like '" + key + "';"
			cursor.execute(sql)
			result = cursor.fetchall()
			if len(result) == 0:
				sql = "insert into term_num(term,num) values('" + key + "',1);"
				cursor.execute(sql)
				connector.commit()
			else:
				sql = "update term_num set num  = " + str(result[0][0]+1) + " where term = '" + key + "';"
				cursor.execute(sql)
				connector.commit()
		#tweet数を格納
		sql = "select * from tweet_num;"
		cursor.execute(sql)
		result = cursor.fetchall()
		sql = "update tweet_num set num = " + str(result[0][0] + 1) + ";"
	finally:
		cursor.execute(sql)
		connector.commit()

	if int(result[0][0]) % 2500 == 0:
		#100万ツイートごとに1回だけ登場の単語はすべて削除
		sql = "delete from term_num where num < 2;"
		cursor.execute(sql)
	cursor.close()
	connector.close()
	print "storage fin..."

##################
##宛先ユーザのを消す##
##################
def mentionCut(txt1):
	twtxt = txt1
	temp = re.split("@+\w+",twtxt)
	twtxt = ""
	for tmp in temp:
		twtxt += tmp
	#print
	#print twtxt
	#print
	return twtxt

##########################################
##URLが名詞にヒットするので、切り取っておく##
##########################################
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
	#print
	#print twtxt
	#print
	return twtxt

###############
##ツイート取得##
###############
class CustomStreamListener(tweepy.StreamListener):
	def on_status(self, status):
		global twDict 
		global twNum
		global txt
		# ひらがな、カタカナが一文字でもあれば簡易的に日本語のTLとする
#		try:
		if(re.match(u'[ぁ-ん]+|[ァ-ヴー]+', status.text)):
			#print status.text.decode("utf-8"),
			print twNum
			txt += status.text.encode('utf-8') + ' '
			#print txt
			if "@" in txt:
				txt = mentionCut(txt)
			if "http" in txt:
				txt = urlCut(txt)
			twNum += 1
			if (twNum%400)==0:
				getKeyword(txt)
				txt = ''
#		except Exception as e:
#		    print '=== エラー内容 ==='
#		    print 'type:' + str(type(e))
#		    print 'args:' + str(e.args)
#		    print 'message:' + e.message
#		    print 'e自身:' + str(e)

	def on_error(self, status_code):
		print >> sys.stderr, 'Encounted Exception with status code:', status_code
		if str(status_code) == "420":
			print "code:420だから10分寝るわ。"
			time.sleep(600)
		return True
	def on_timeout(self):
		print >> sys.stderr, 'Timeout...'
		return True

def main():
	global auth
	global api
	stream = tweepy.Stream(auth, CustomStreamListener(),timeout=None)
	print >> sys.stderr, 'Filtering the public timeline for "%s"' % (''.join(sys.argv[1:]),)
	#Public TLからワードを指定して取り出す場合、引数にワードを指定し、この関数を利用する
	#streaming_api.filter(follow=None, track=Q)
	#何も指定せず、ただPublic TLのみを取り出す場合は、この関数を利用する
	stream.sample()

if  __name__ == "__main__":
	for cnt in range(10):
		print "実行回数", cnt
		try:
			main()
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
