#!/usr/local/bin/python3
# import users from a csv file

import sys
import csv
import requests
import json

# Create a file which will contains the errors from the API responses
file = open("import_users_errors.txt","w+")

# Ask the user for the email address and rest api key
requester = input('Enter requester email address (must be email address from an existing PD user): ')
key = input('Enter REST API key (must *not* be read-only key): ')

# Initialize constants for the API requests
base_url = "https://api.pagerduty.com"
header_without_requester = {
	"Content-Type": "application/json",
	"Authorization": "Token token=" + key,
	"Accept": "application/vnd.pagerduty+json;version=2"
}
header_with_requester = {
	"Content-Type": "application/json",
	"Authorization": "Token token=" + key,
    "Accept": "application/vnd.pagerduty+json;version=2",
	"From": requester
}
request = requests.Session()

# See if user wants to create a team if they don't exist, and initiate the boolean variable to execute on this later in the script
create_team_option = input("Create teams if they don't exist? (type 'yes' or 'no'): ")
if create_team_option.lower() == 'yes':
	create_team_option = True
else: 
	create_team_option = False


# API request to create the user
def base_user(user):
	body = {
		"user": {
			"type": "user",
			"name": user.name,
			"email": user.email,
			"role": user.role,
			"job_title": user.title}
	}
	request.headers.update(header_with_requester)
	response = request.post(base_url + '/users',data=json.dumps(body))

	if response.status_code == 201:
		user.id = (response.json()['user']['id'])
		return True
	else:
		file.write("'" + user.name + "'" + " was not created because of error(s) " + response.text + "\n")
		return False

# API request to add the contact method and notification rules on the specific channel (SMS or Phone)
def add_contact_and_notification_objects(user,channel):
	body =  { 
		"contact_method": {
				"type": channel + "_contact_method",
				"label": "Mobile",
				"address": user.phone_number,
				"country_code":user.phone_country_code}
		}
	request.headers.update(header_without_requester)
	response = request.post(base_url + '/users/' + user.id + '/contact_methods', data=json.dumps(body))

	if response.status_code == 201:
		contact_method_id = response.json()['contact_method']['id']
		body = {
			"notification_rule": {
				"type": "assignment_notification_rule",
				"start_delay_in_minutes": 0,
				"contact_method": {
						"id":contact_method_id,
						"type": channel + "_contact_method"
						},
				"urgency": "high"
				}
			}
		response = request.post(base_url + '/users/' + user.id + '/notification_rules', data=json.dumps(body))
	else:
		file.write(channel + " contact method not added for " + user.name + " because of error(s): " + response.text + "\n")

# API request to add the user to the team
def add_user_to_team(user,team):
	request.headers.update(header_without_requester)

	#paginate incase an account has a lot of teams
	team_list = {}
	offset = 0
	while True: 
		response = request.get(base_url + '/teams?query=' + team + '&limit=100&offset=' + str(offset))
		for each_team in response.json()['teams']:
			team_list.update({each_team['summary'].lower():each_team['id']})
		if response.json()['more'] == False:
			break
		else:
			offset += 100
		
	# If user chose the option to Not create a team
	if create_team_option != True:
		if team_list.get(team.lower()):
			return request.put(base_url + '/teams/' + team_list.get(team.lower()) + '/users/' + user.id)
		file.write('no existing team found for ' + team + '\n')

	# If user chose the option to create a team if it does not currently exist
	else: 
		if team_list.get(team.lower()):
			return request.put(base_url + '/teams/' + team_list.get(team.lower()) + '/users/' + user.id)
		# create a team if is does not exist
		else:
			body = {
					"team": {
						"type": "team",
						"name": team
					}
				}
			response = request.post(base_url + '/teams', data=json.dumps(body))
			file.write('created team "' + team + ' "because no team existed' + '\n')
			team_id = response.json()['team']['id']
			response = request.put(base_url + '/teams/' + team_id + '/users/' + user.id)
		
# Clean up the text of the 'user' role to satisfy the API request
def sanitize(role):
	if role == "":
		return 'user'
	else:
		role = role.replace(' ','_') # incase the csv file has, for example, "read only user" as the role
		if (role == 'stakeholder' or role == 'read_only_user'):
			return 'read_only_user'
		elif (role == 'responder' or role == 'limited_user'):
			return 'limited_user'
		else: 
			return role

class Users:
	def __init__(self,name,email,role,title,phone_country_code,phone_number,team):
		self.name = name.strip()
		self.email = email.strip()
		self.role = sanitize(role.strip().lower())
		self.title = title.strip() or " "
		self.phone_country_code = phone_country_code.strip()
		self.phone_number = phone_number.strip()
		self.team = team.strip()

	def create_base_user(self):
		return base_user(self)	

	def add_contact_method(self,channel):
		add_contact_and_notification_objects(self,channel)
	
	def add_team(self,team):
		if team == "":
			return
		else:
			add_user_to_team(self,team)
		

with open('users.csv') as csvfile:
	reader = csv.DictReader(csvfile, fieldnames=("name","email","role","title","phone_country_code","phone_number","team"))
	next(reader)

	for row in reader: 
		if (row['name'] == '') or (row['email'] == ''):
			continue
		
		else:
			user = Users(row['name'],row['email'],row['role'],row['title'],row['phone_country_code'],row['phone_number'],row['team'])
			user_created = user.create_base_user() # return False if user was not created
			
			if user_created == False: 
				continue # end loop and go to next line in CSV incase this line/user was not created
			
			if user.team != '':
				user.add_contact_method("phone")
				user.add_contact_method("sms")

			if ';' in user.team:
				all_teams = user.team.split(';')
				for team in all_teams:
					user.add_team(team)
			else:
				user.add_team(user.team)
			print(row['name'] + ' was added')

print('\n')
print('Script has finished running.')
input('Did you delete the API key from the customers account?!: ')