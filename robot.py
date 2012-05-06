from tornado.httpclient import HTTPClient
from tornado.httpclient import AsyncHTTPClient
from time import gmtime, strftime
from poker_controller import *
import tornado.ioloop
import urllib
import json
import pprint
import array

(A_ALLIN,A_CALLSTAKE,A_RAISESTAKE,A_CHECK,A_DISCARDGAME,A_BIGBLIND,A_SMALLBLIND,A_STANDUP) = (1,2,3,4,5,6,7,8)
class Seat:
	def __init__(self, seat_id = -1, stake = 0, table = 0):
		self.id			= seat_id
		self.stake		= stake
		self.table		= table
		self.hand_cards	= []

class DecisionMaker:
	def __init__(self):
		self.ranks	= {}
		self.poker	= Poker(2)
		self.cards	= []
		suit		= 0x8000;
		index		= 0
		for i in xrange(4):
			for j in xrange(2,15):
				self.cards.append(Card(i,j))

	def _rank_compare(self, left,right):
		if left[0] != right[0] :
			return left[0] - right[0]
		else:
			for i in xrange(len(left[1])):
				if left[1][i] != right[1][i]:
					return left[1][i] - right[1][i]
		return 0

	def convert_to_deck(self, card):
		_suit = 0
		_value= 0
		if len(card) == 2:
			_value= card[0]
			_suit = card[1]
		elif len(card) == 3:
			_value= "10"
			_suit = card[2]

		if _value.isdigit():
			_value = int(_value)
		else:
			if _value == "J":
				_value = 11
			elif _value == "Q":
				_value = 12
			elif _value == "K":
				_value = 13
			elif _value == "A":
				_value = 14

		if _suit == "C":
			_suit = 0
		elif _suit == "D":
			_suit = 1
		elif _suit == "H":
			_suit = 2
		elif _suit == "S":
			_suit = 3
		return Card(_suit, _value)


	def _rank(self, cards):
		cards.sort()
		return self.poker.score(cards)

	def filter(self,source, exclude_list):
		result	= []
		flag	= False
		for element in source:
			for item in exclude_list:
				if element.symbol == item.symbol and  element.value == item.value :
					flag = True
					break;
			if flag == False:
				result.append(element)
			flag = False
		return result
	def _chen_score(self, card):
		if card.value == 14:
			return 10
		elif card.value == 13:
			return 8
		elif card.value == 12:
			return 7
		elif card.value == 11:
			return 6
		else:
			return card.value / 2.0

	def _chen_formula(self, cards):
		baseScore = max(self._chen_score(cards[0]), self._chen_score(cards[1]))
		if cards[0].value == cards[1].value:
			baseScore = max(5, baseScore * 2)

		if cards[0].symbol == cards[1].symbol:
			baseScore += 2

		gap = abs(cards[0].value - cards[1].value)
		if gap == 0:
			pass
		elif gap == 1:
			baseScore	+= 1
		elif gap == 2:
			baseScore	-= 1
		elif gap == 3:
			baseScore	-= 2
		elif gap == 4:
			baseScore	-= 4
		else:
			baseScore	-= 5

		return (baseScore - gap)/20.0;


	def _hand_potential(self, robot_cards, opp_cards_list, board_cards):
		total_cases	= 0
		win_counter	= 0
		if len(board_cards) >0:
			robot_all_cards = robot_cards + board_cards
			remain_cards	= self.filter(self.cards, robot_all_cards)
			for opp_cards in opp_cards_list:
				remain_cards= self.filter(remain_cards, opp_cards)

		if len(board_cards) == 0:
			return self._chen_formula(robot_cards)
		elif len(board_cards) == 3:
			for k in xrange(len(remain_cards)-1):
				for o in xrange(k + 1, len(remain_cards)):
					counter = 0
					for opp_cards in opp_cards_list:
						temp_board	= board_cards + [remain_cards[k], remain_cards[o]]
						robot_best	= self._rank(temp_board + robot_cards)
						opp_best	= self._rank(temp_board + opp_cards)
						best_comparison = self._rank_compare(robot_best, opp_best)
						if best_comparison > 0:
							counter += 1
				total_cases += 1
				if counter == len(opp_cards_list):
					win_counter += 1
		elif len(board_cards) == 4:
			for k in xrange(len(remain_cards)):
				counter = 0
				for opp_cards in opp_cards_list:
					temp_board	= board_cards + [remain_cards[k]]
					robot_best	= self._rank(temp_board + robot_cards)
					opp_best	= self._rank(temp_board + opp_cards)
					best_comparison = self._rank_compare(robot_best, opp_best)
					if best_comparison > 0:
						counter += 1
				total_cases += 1
				if counter == len(opp_cards_list):
					win_counter += 1
		elif len(board_cards) == 5:
			remain_cards= self.filter(self.cards, robot_all_cards)
			no_opp		= len(opp_cards_list)
			for i in xrange(len(remain_cards) - no_opp - 1):
				for j in xrange(i + 1, len(remain_cards) - no_opp ):
					counter = 0
					for k in xrange(no_opp):
						temp_board	= board_cards + [remain_cards[i], remain_cards[j + k]]
						robot_best	= self._rank(temp_board + robot_cards)
						opp_best	= self._rank(temp_board + opp_cards)
						best_comparison = self._rank_compare(robot_best, opp_best)
						if best_comparison > 0:
							counter += 1
					total_cases += 1
				if counter == no_opp:
					win_counter += 1

		return (win_counter*1.0)/total_cases


	def make_decision(self, robot_cards, opp_cards_list, board_cards, current_pot, call_stake, min_raise, max_raise, rights):
		robot_decks		= []
		board_decks		= []
		opp_decks_list	= []
		print "======================[start]==========================="
		print robot_cards
		print board_cards
		print opp_cards_list
		print "======================[end]==========================="
		for card in robot_cards:
			robot_decks.append(self.convert_to_deck(card))
		print "=======1====="
		for card in board_cards:
			board_decks.append(self.convert_to_deck(card))

		print "=======2====="
		for cards in opp_cards_list:
			temp_list	= []
			for card in cards:
				temp_list.append(self.convert_to_deck(card))
			opp_decks_list.append(temp_list)
		print "=======3====="

		print opp_decks_list
		win_probability = self._hand_potential(robot_decks, opp_decks_list, board_decks)
		win_probability += 0.005
		if win_probability > 1.0:
			win_probability = 1.0
		win_odds = 1.0 / (win_probability)
		print win_probability
		print win_odds

		amount = -1
		action = -1

		if A_CALLSTAKE in rights and A_ALLIN in rights and A_RAISESTAKE not in rights:
			if current_pot / call_stake > win_odds :
				if current_pot / max_raise > win_odds:
					print "max raise all in"
					amount = max_raise
					action = A_ALLIN
				else:
					print "call stake"
					amount = call_stake
					action = A_CALLSTAKE
			else:
				print "fold"
				amount = -1
				action = A_DISCARDGAME

		elif A_CALLSTAKE in rights and A_RAISESTAKE in rights:
			if current_pot / call_stake > win_odds :
				if current_pot / max_raise > win_odds:
					print "max raise all in"
					amount = max_raise
					action = A_RAISESTAKE
				elif current_pot / min_raise > win_odds:
					print "min raise"
					amount = min_raise
					action = A_RAISESTAKE
				else:
					print "call stake"
					amount = call_stake
					action = A_CALLSTAKE
			else:
				print "fold"
				amount = -1
				action = A_DISCARDGAME

		elif A_CALLSTAKE not in rights and A_ALLIN in rights:
			if current_pot / min_raise > win_odds:
				print "min raise"
				amount = min_raise
				action = A_RAISESTAKE
			else:
				print "fold"
				amount = -1
				action = A_DISCARDGAME

		if amount == -1 and A_CHECK in rights:
			amount = -1
			action = A_CHECK

		if action == A_ALLIN and len(board_decks) <3:
			action = A_CALLSTAKE
			amount = call_stake
		print "amount = ",amount
		return (action, amount)


class Robot:
	Login_URL_Template					= "http://%s:%d/login"
	List_Room_URL_Template				= "http://%s:%d/list_room"
	Enter_Room_URL_Template				= "http://%s:%d/enter"
	User_Info_URL_Template				= "http://%s:%d/userinfo"
	Sit_Down_URL_Template				= "http://%s:%d/sit-down"
	Post_Board_Message_URL_Template		= "http://%s:%d/post-board-message"
	Listen_Board_Message_URL_Template	= "http://%s:%d/listen-board-message"
	Action_ALL			= 1
	Action_Call_Stake	= 2
	Action_Raise_Stake	= 3
	Action_Check_Stake	= 4
	Action_Discard_Game	= 5
	Action_Stand_Up		= 8
	def __init__(self, ip='127.0.0.1', port = 80, username=None, password=None, room=None):
		self.ip			= ip
		self.port		= port
		self.username	= username
		self.password	= password
		self.room			= None
		self.timestamp		= -1
		self.public_cards	= [0, 0, 0, 0, 0]
		self.seats			= [0, 0, 0, 0, 0, 0, 0, 0, 0]
		self.seat			= -1
		self.pot_amount		= 0
		self.min_raise		= 0
		self.max_raise		= 0
		self.call_amount	= 0
		self.hand_cards		= None
		self.rights			= None
		self.opp_cards		= None
		self.http_client	= AsyncHTTPClient()
		self.decision_maker = DecisionMaker()
		self.login_url		= Robot.Login_URL_Template % (ip, port)
		self.enter_url		= Robot.Enter_Room_URL_Template % (ip, port)
		self.user_info_url	= Robot.User_Info_URL_Template % (ip, port)
		self.list_room_url	= Robot.List_Room_URL_Template % (ip, port)
		self.sit_down_url				= Robot.Sit_Down_URL_Template % (ip, port)
		self.post_board_message_url		= Robot.Post_Board_Message_URL_Template % (ip ,port)
		self.listen_board_message_url	= Robot.Listen_Board_Message_URL_Template % (ip, port)

	def start(self):
		print "Robot login [start]"
		post_data	= {"username":self.username, "password":self.password}
		body		= urllib.urlencode(post_data)
		self.http_client.fetch(self.login_url,
								self.login_handle,
								method='POST',
								headers=None,
								body=body)
		print "Robot login [end]"

	def login_handle(self,response):
		print "Robot login handle [start]"
		content		= json.loads(response.body)
		if content["status"] == "success":
			self.cookies= response.headers['Set-Cookie'];
			self.get_user_info()
		else:
			pass
		print "Robot login handle [end]"

	def get_user_info(self):
		headers	= {"Cookie":self.cookies}
		self.http_client.fetch(	self.user_info_url,
								self.user_info_handle,
								method='GET',
								headers=headers)

	def user_info_handle(self,response):
		content		= json.loads(response.body)
		self.asset	= content['s']
		self.list_room()

	def list_room(self):
		headers	= {"Cookie":self.cookies}
		body	= urllib.urlencode({"type":0})
		self.http_client.fetch(	self.list_room_url,
								self.list_room_handle,
								method='POST',
								headers=headers,
								body=body)

	def list_room_handle(self, response):
		def sorter(left, right):
			return left[2] - right[2]

		print "List Room Handle[start]"
		print response.body
		content = json.loads(response.body)
		available_list = filter(lambda x: x[2] > 0 and x[2] < x[3] ,content["rooms"])
		print available_list
		if len(available_list) > 0:
			available_list.sort(sorter)
			self.room = available_list[0][0]
		else:
			self.room = content["rooms"][0][0]

		self.enter()
		print "List Room Hanlde[end]"

	def enter(self):
		print "Robot enter [start]"
		post_data	= {"room_id":self.room}
		body		= urllib.urlencode(post_data)
		headers		= {"Cookie":self.cookies}
		self.http_client.fetch(	self.enter_url,
								self.enter_handle,
								method='POST',
								headers=headers,
								body=body)
		print "Robot enter [end]"

	def enter_handle(self, response):
		print "Robot enter handle [start]"
		print response.body
		content		= json.loads(response.body)
		if content["status"] == "success":
			self.cookies= response.headers['Set-Cookie'];
			self.min_stake	= content["room"]["min_stake"]
			self.max_stake	= content["room"]["max_stake"]
			for i in xrange(len(content["room"]["seats"])):
				if content["room"]["seats"][i] == None:
					self.seat = i

			if self.asset > (self.min_stake+self.max_stake)/2:
				self.stake	= (self.min_stake+self.max_stake)/2
			else:
				self.stake	= self.min_stake

			self.asset	-= self.stake
			self.sit_down()
		else:
			pass
		print "Robot enter handle [end]"


	def sit_down(self):
		print "Robot sit_down  [start]"
		post_data	= {"seat": self.seat, "stake":self.stake}
		body		= urllib.urlencode(post_data)
		headers		= {"Cookie":self.cookies}
		self.http_client.fetch(	self.sit_down_url,
								self.sit_down_handle,
								method	= "POST",
								headers	= headers,
								body	= body)

		print "Robot sit_down [end]"

	def sit_down_handle(self,response):
		print "Robot sit_down handle [start]"
		content		= json.loads(response.body)
		if content["status"] == "success":
			self.cookies= response.headers['Set-Cookie'];
			self.listen_board_message()
		else:
			pass
		print "Robot sit_down handle [end]"

	def listen_board_message(self):
		print "Robot listen board message [start]"
		post_data	= {"timestamp": self.timestamp}
		body		= urllib.urlencode(post_data)
		headers		= {"Cookie":self.cookies}

		print "post content"
		print post_data
		self.http_client.fetch(	self.listen_board_message_url,
								self.listen_board_message_handle,
								method	= "POST",
								headers	= headers,
								body	= body)

		print "Robot listen board message [end]"

	def listen_board_message_handle(self, response):
		print "Robot listen board message handle [start]"
		print response.body
		try:
			content	= json.loads(response.body)
			content.sort(self._sorter)
			self.cookies= response.headers['Set-Cookie'];
			for i in xrange(len(content)):
				message			= content[i]
				print message
				self.timestamp	= message["timestamp"]
				method = getattr(self,"handle_" + message['msgType'])
				method(message)
		except:
			print "Unexpected error:", sys.exc_info()[0]
			print "content is :"
			print response.body

		self.listen_board_message()
		print "Robot listen board message handle [end]"

	def _sorter(self, left, right):
		return left["timestamp"] - right["timestamp"]

	def send_post_message(self):
		print "send post message [start]"
		(action, amount)  = self.decision_maker.make_decision(
											self.hand_cards,
											self.opp_cards,
											self.public_cards,
											self.pot_amount,
											self.call_amount,
											self.min_raise,
											self.max_raise,
											self.rights)

		post_data	= {"message":json.dumps({"action": action, "amount":amount})}
		body		= urllib.urlencode(post_data)
		headers		= {"Cookie":self.cookies}
		self.http_client.fetch(	self.post_board_message_url,
								self.handle_post_board,
								method	= "POST",
								headers	= headers,
								body	= body)

	#print decision_maker.make_decision(cards, opp_card_list, p_cards, 200, 10,20,100,["call", "raise"])
		print "send post message [end]"


	def handle_post_board(self, data):
		print "handle post message [start]"
		print data.body
		print "handle post message [end]"

	def handle_sit(self,data):
		print "handle sit [start]"
		self.seats[data["seat_no"]] = Seat()
		self.seats[data["seat_no"]].seat_id = data["seat_no"]
		self.seats[data["seat_no"]].stake = data["info"]["player_stake"]
		self.seats[data["seat_no"]].table = 0
		print "handle sit [end]"

	def handle_bot_card(self, data):
		print "handle bot card [start]"
		print data
		if data['cards'] not in self.opp_cards:
			self.opp_cards.append(data['cards'])
		print "handle bot card [end]"

	def handle_bhc(self,data):
		print "handle bhc [start]"
		print data
		pass
		print "handle bhc [end]"

	def handle_phc(self,data):
		print "handle phc [start]"
		print data
		self.hand_cards = data["cards"]
		pass
		print "handle phc [end]"

	def handle_winner(self,data):
		print "handle winner [start]"
		print data
		if data[self.room]["seat_no"] ==self.seat_no:
			self.asset	+= data[self.room]['stake'] - self.stake
			self.stake	= data[self.room]['stake']
		print "handle winner [end]"

	def handle_next(self,data):
		print "handle next [start]"
		print "seat no =%d"%(data["seat_no"])
		print "self seat=%d"%(self.seat)
		if data["seat_no"] == self.seat:
			if 2 in data["rights"]:
				self.call_amount= data["amount_limits"]['2']
			if 3 in data["rights"]:
				self.min_raise	= data["amount_limits"]['3'][0]
				self.max_raise	= data["amount_limits"]['3'][1]
			self.rights = data["rights"]
			self.send_post_message()
		print "handle next [end]"

	def handle_action(self, data):
		print "handle action [start]"
		if data["seat_no"] == self.seat:
			self.stake = data["stake"]
		print "handle action [end]"

	def handle_public(self,data):
		print "handle public [start]"
		self.public_cards = []
		for i in xrange(len(data["cards"])):
			self.public_cards.append(data["cards"][i]);
		print "handle public [end]"

	def handle_start(self,data):
		print "handle start game [start]"
		self.public_cards	= []
		self.opp_cards		= []
		self.hand_cards		= []
		self.pot_amount		= 0
		print "stake =>",self.stake
		print "handle start game [end]"

	def handle_pot(self, data):
		print "handle pot [start]"
		self.pot_amount = 0
		for pot in data["pot"]:
			self.pot_amount += pot[1]["amount"]
		print "handle pot [end]"


	def handle_standup(self, data):
		print "handle stand up [start]"
		stand_up_player = filter(lambda x: "seat_no" in x,data)
		for player in stand_up_player:
			self.seat[player["seat_no"]] = None
		print "handle stand up [end]"


if __name__=="__main__":
	robot	= Robot(ip='127.0.0.1',port=8888,username='bot1',password='123321')
	robot.start()
	ioloop	= tornado.ioloop.IOLoop.instance()
	ioloop.start()
	'''
	decision_maker	= DecisionMaker()
	cards	= ["2C", "2D"]
	p_cards	= ["5H", "4S", "6C",]
	opp_card_list = [["3D","KD"], ["3S","4H"], ["2S","AD"]]
	print strftime("%Y-%m-%d %H:%M:%S", gmtime())
	print decision_maker.make_decision(cards, opp_card_list, p_cards, 200, 10,20,100,["call", "raise"])
	print strftime("%Y-%m-%d %H:%M:%S", gmtime())
	print decision_maker.make_decision(cards, opp_card_list, p_cards, 200, 40,80,100,["call", "raise"])
	print strftime("%Y-%m-%d %H:%M:%S", gmtime())
	'''