from riotwatcher import RiotWatcher
from collections import defaultdict
from json import load, dump
import os
from datetime import datetime, timedelta
from riotwatcher import LoLException, error_404, error_429
import time

with open('key.txt', 'r') as f:
	key = f.read()

divisions = ['BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND', 'MASTER', 'CHALLENGER']

game_ids_by_division = defaultdict(lambda : set())
summoner_ids_by_division = defaultdict(lambda : set())
processed_game_counts_by_division = {division : 0 for division in divisions}
processed_summoner_ids = set()
processed_game_ids = set()


def totimestamp(dt, epoch=datetime(1970,1,1)):
    td = dt - epoch
    # return td.total_seconds()
    return float(td.microseconds + (td.seconds + td.days * 86400) * 10**6) / 10**3 

patch_date = datetime(2017, 3, 3)



class Request:

	def __init__(self, request_queue):
		self.request_queue = request_queue


	def make_request(self, rw):
		raise NotImplementedError

class GameRequest(Request):

	def __init__(self, request_queue, game_id):
		Request.__init__(self, request_queue)
		self.game_id = game_id 

	def make_request(self, rw):
		match = rw.get_match(self.game_id)
		with open(os.path.join('data/games2/', '%s.json' % self.game_id), 'w') as fp:
			dump(match, fp, indent = 4, separators = (',', ': '))

		participants = match["participantIdentities"]
		summoner_ids = [participant["player"]["summonerId"] for participant in participants]
		
		self.request_queue.append(SummonerDivisionRequest(self.request_queue, self.game_id, summoner_ids))



class SummonerMatchListRequest(Request):

	def __init__(self, request_queue, summoner_id, division):
		Request.__init__(self, request_queue)
		self.summoner_id = summoner_id
		self.division = division

	def make_request(self, rw):
		json_body = rw.get_match_list(self.summoner_id, ranked_queues = 'RANKED_SOLO_5x5,TEAM_BUILDER_DRAFT_RANKED_5x5,TEAM_BUILDER_RANKED_SOLO')
		if "matches" in json_body:
			matches = json_body["matches"]
			for match in matches:
				if match["timestamp"] > totimestamp(patch_date):
					match_id = match["matchId"]
					game_ids_by_division[self.division].add(match_id)




division_to_base_elo = {'BRONZE' : 800, 'SILVER' : 1150, 'GOLD' : 1500, 'PLATINUM' : 1850, 'DIAMOND' : 2200, 'MASTER' : 2550, 'CHALLENGER' : 2700}
tier_increases = {'V' : 0, 'IV' : 70, 'III' : 140, 'II' : 210, 'I' : 280}
def get_elo_from_division_tier(division, tier):
	if division in ['CHALLENGER', 'MASTER']:
		return division_to_base_elo[division]
	return division_to_base_elo[division] + tier_increases[tier]

# Loops through the divisions body and looks for the ranked solo 5x5 division.
def get_elo_from_player_json(divisions):
	for ranking in divisions:
		if ranking["queue"] == "RANKED_SOLO_5x5":
			if "entries" in ranking:
				tier = ranking["entries"][0]["division"]
				division = ranking["tier"]
				return get_elo_from_division_tier(division, tier)

def get_elo_from_division_request(json_body):
	total_elo = 0
	num_ranked_players = 0
	for summoner_id, divisions in json_body.items():
		summoner_elo = get_elo_from_player_json(divisions)
		if summoner_elo is not None:
			num_ranked_players += 1
			total_elo += summoner_elo
			# TODO add summarizing statistics?

	return float(total_elo) / num_ranked_players

def get_elo_bucket_from_true_elo(game_elo):
	if game_elo >= 2600:
		return 'CHALLENGER'
	else:
		return divisions[int((game_elo - 800) / 350)]


class SummonerDivisionRequest(Request):
	# Requests a summoner's overall statistics and its divisions.
	def __init__(self, request_queue, game_id, summoner_ids):
		Request.__init__(self, request_queue)
		self.summoner_ids = summoner_ids 
		self.game_id = game_id

	def make_request(self, rw):
		json_body = rw.get_league_entry(self.summoner_ids)
		game_elo = get_elo_from_division_request(json_body)

		elo_bucket = get_elo_bucket_from_true_elo(game_elo)
		processed_game_counts_by_division[elo_bucket] += 1

		for summoner_id, divisions in json_body.items():
			summoner_elo = get_elo_from_player_json(divisions)
			if summoner_elo is not None:
				summoner_bucket = get_elo_bucket_from_true_elo(summoner_elo)
				summoner_ids_by_division[summoner_bucket].add(summoner_id)

		with open(os.path.join('data/summoner_divisions2', '%s.json' % self.game_id), 'w') as fp:
			dump(json_body, fp, indent = 4, separators = (',', ': '))



class RequestDecider:

	def __init__(self, initial_summoner_list, intiial_game_list):
		self.request_queue = []	
		global summoner_ids_by_division
		summoner_ids_by_division = {k : set(v) for (k, v) in initial_summoner_list.items()}

	def get_next_request(self):
		if len(self.request_queue) == 0:
			# Look up the best game from those currently available.
			desired_division = min(divisions, key = lambda division : processed_game_counts_by_division[division])
			if len(game_ids_by_division[desired_division]) == 0:
				# We need to collect more games at this division.
				try:
					summoner_id = summoner_ids_by_division[desired_division].pop()
				except KeyError:
					print "Don't have enough players in the %s division." % desired_division
					exit(0)
				processed_summoner_ids.add(summoner_id)
				return SummonerMatchListRequest(self.request_queue, summoner_id, desired_division)

			else:
				game_id = game_ids_by_division[desired_division].pop()
				if game_id in processed_game_ids:
					return self.get_next_request()

				processed_game_ids.add(game_id)
				return GameRequest(self.request_queue, game_id)

		else:
			request = self.request_queue.pop()
			return request

if __name__ == '__main__':
	rw = RiotWatcher(key)

	initial_summoner_ids = {'BRONZE' : [43910145, 70283319, 29267527], 'SILVER' : [69362057, 37384719, 21880129, 65751659, 47172330], 'GOLD' : [28119202, 51784114], 'PLATINUM' : [49159160, 183802, 51891458], 'DIAMOND' : [19245322, 31559474], 'MASTER' : [36653735], 'CHALLENGER' : [35590582]}
	initial_game_list = []
	request_decider = RequestDecider(initial_summoner_ids, initial_game_list)
	while True:
		try:
			print 'making request'
			print 'game counts: %s' % processed_game_counts_by_division
			request = request_decider.get_next_request()
			request.make_request(rw)

		except LoLException as e:
			if e == error_429:
				print 'sleeping for %s seconds' % e.headers['Retry-After']
				request_decider.request_queue.append(request)
				time.sleep(int(e.headers['Retry-After']))

