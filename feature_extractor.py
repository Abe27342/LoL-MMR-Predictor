from json import load

'''
features to do:

ward information

items

summoner spells

tower damage

dragons

barons

tower kills

game length

cs 

cs per minute

'''


with open('data/static/champions.json') as fp:
    champions_json = load(fp)
    champion_ids = [champion["id"] for champion in champions_json["data"].values()]
    champion_ids_to_champion_one_hot_dict = {v : k for k, v in enumerate(champion_ids)}

with open('data/static/items.json') as fp:
    items_json = load(fp)
    item_ids = [item["id"] for item in items_json["data"].values()]
    item_ids_to_item_one_hot_dict = {v : k for k, v in enumerate(item_ids)}

class FeatureExtractor:
    '''
    Class that gets a feature vector from a given textline. To add features, simply define any new method
    that starts with "_f" and takes in a text line. You'll need to train a new model when doing this.
    '''

    def get_team_picks(self, participants, team_id):
        team_picks = []
        for participant in participants:
            if participant["teamId"] == team_id:
                team_picks.append(participant["championId"])
        return team_picks


    def bucket_real(self, value, bucket_separators):
        assert len(bucket_separators) > 0
        buckets = [0] * (len(bucket_separators) + 1)
        if value < bucket_separators[0]:
            buckets[0] = 1
        for i in range(len(bucket_separators) - 1):
            if bucket_separators[i] <= value < bucket_separators[i + 1]:
                buckets[i + 1] = 1
        if bucket_separators[-1] <= value:
            buckets[-1] = 1

        return buckets

    def one_hot_encode(self, ids, riot_id_to_encoding_dict):
        encoding = [0] * len(riot_id_to_encoding_dict)
        for id in ids:
            encoding[riot_id_to_encoding_dict[id]] = 1
        return encoding


    def _f1(self, json_document):
        feature_vector = []

        team1, team2 = json_document["teams"]
        bans = [turn["championId"] for turn in team1["bans"]] + [turn["championId"] for turn in team2["bans"]]

        team1_id = team1["teamId"]
        team2_id = team2["teamId"]

        team1_picks = self.get_team_picks(json_document["participants"], team1_id)
        team2_picks = self.get_team_picks(json_document["participants"], team2_id)

        feature_vector.extend(self.one_hot_encode(bans, champion_ids_to_champion_one_hot_dict))
        feature_vector.extend(self.one_hot_encode(team1_picks, champion_ids_to_champion_one_hot_dict))
        feature_vector.extend(self.one_hot_encode(team2_picks, champion_ids_to_champion_one_hot_dict))

        return feature_vector


    def _f2(self, json_document):
        match_duration = json_document["matchDuration"]

        ward_vector = []

        wards_placed = 0
        vision_wards_bought = 0
        wards_killed = 0

        for participant in json_document["participants"]:
            participant_stats = participant["stats"]
            wards_placed += participant_stats["wardsPlaced"]
            vision_wards_bought += participant_stats["visionWardsBoughtInGame"]
            sight_wards_bought = participant_stats["sightWardsBoughtInGame"]
            wards_killed += participant_stats["wardsKilled"]

        wards_placed = wards_placed / 10.0
        vision_wards_bought = vision_wards_bought / 10.0
        wards_killed = wards_killed / 10.0

        ward_vector.extend(self.bucket_real((60.0 * wards_placed) / match_duration, [i / 100.0 for i in range(1, 70)]))
        ward_vector.extend(self.bucket_real(vision_wards_bought, [i for i in range(1, 10)]))
        ward_vector.extend(self.bucket_real(wards_killed, [i / 2.0 for i in range(1, 20)]))

        return ward_vector


    def _f3(self, json_document):
        match_duration = json_document["matchDuration"]

        cs_vector = []
        minions_killed = 0
        for participant in json_document["participants"]:
            participant_stats = participant["stats"]
            minions_killed += participant_stats["minionsKilled"]

        minions_killed = float(minions_killed) / 10
        cs_vector.extend(self.bucket_real((60.0 * minions_killed) / match_duration, [i for i in xrange(1, 13)]))

        return cs_vector

    def _f4(self, json_document):
        all_items = []
        for participant in json_document["participants"]:
            participant_stats = participant["stats"]
            for i in range(7):
                potential_item = participant_stats["item%s" % i]
                if potential_item != 0:
                    all_items.append(potential_item)

        return self.one_hot_encode(all_items, item_ids_to_item_one_hot_dict)


    '''
    def _f5(self, json_document):
        da_vector = []
        total_deaths = 0
        total_assists = 0
        for participant in json_document["participants"]:
            participant_stats = participant["stats"]
            total_deaths += participant_stats["deaths"]
            total_assists += participant_stats["assists"]

        da_vector.extend(self.bucket_real(float(total_assists + .0001) / (total_deaths + .0001), [i / 10.0 for i in xrange(1, 10)] + [i / 4 for i in range(4, 32)]))

        return da_vector
    '''


    def get_feature_vector(self, json_document):
        feature_vector = []
        for func in dir(self):
            if callable(getattr(self, func)) and func.startswith('_f'):
                feature_vector_val = getattr(FeatureExtractor, func)(self, json_document)
                feature_vector.extend(feature_vector_val)
        return feature_vector