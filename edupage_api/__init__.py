from datetime import date
import requests, json, datetime, pprint

from edupage_api.utils import *
from edupage_api.date import EduLength
from edupage_api.timetables import *
from edupage_api.messages import EduHomework, EduNews
from edupage_api.grades import EduGradeEvent
from edupage_api.people import EduStudent

class Edupage:
	def __init__(self, username, password):
		self.school = None
		self.username = username
		self.password = password
		self.is_logged_in = False
		self.session = requests.session()
	
	def login(self):
		parameters = {"meno": self.username, "password": self.password, "akcia": "login"}
		response = self.session.post("https://portal.edupage.org/index.php?jwid=jw2&module=Login", parameters)
		if "wrongPassword" in response.url:
			return False
		try:
			js_json = response.content.decode() \
									.split("$j(document).ready(function() {")[1] \
									.split(");")[0] \
									.replace("\t", "") \
									.split("userhome(")[1] \
									.replace("\n", "") \
									.replace("\r", "")
		except TypeError:
			return False
		except IndexError:
			return False
		self.school = response.url.split(".edupage.org")[0] \
								.split("https://")[1]
		self.cookies = response.cookies.get_dict()
		self.headers = response.headers
		self.data = json.loads(js_json)
		self.is_logged_in = True
		self.ids = IdUtil(self.data)
		return True
	
	def get_available_timetable_dates(self):
		if not self.is_logged_in:
			return None
		
		dp = self.data.get("dp")
		if dp == None:
			return None
		
		dates = dp.get("dates")
		return list(dates.keys())

	def get_timetable(self, date):
		if not self.is_logged_in:
			return None
		dp = self.data.get("dp")
		if dp == None:
			return None
			
		dates = dp.get("dates")
		date_plans = dates.get(str(date))
		if date_plans == None:
			return None
		
		plan = date_plans.get("plan")
		subjects = []
		for subj in plan:
			header = subj.get("header")
			if len(header) == 0:
				return subjects
			
			subject_id = subj.get("subjectid")
			subject_name = self.ids.id_to_subject(subject_id)
			
			teacher_id = subj.get("teacherids")[0]
			teacher_full_name = self.ids.id_to_teacher(teacher_id)

			classroom_id = subj.get("classroomids")[0]
			classroom_number = self.ids.id_to_classroom(classroom_id)

			start = subj.get("starttime")
			end = subj.get("endtime")
			length = EduLength(start, end)

			online_lesson_link = subj.get("ol_url")
			
			lesson = EduLesson(subject_name, teacher_full_name, classroom_number, length, online_lesson_link) 
			subjects.append(lesson)

			
		return subjects
	
	def get_homework(self):
		if not self.is_logged_in:
			return None
		
		items = self.data.get("items")
		if items == None:
			return None
		
		ids = IdUtil(self.data)

		homework = []
		for item in items:
			if not item.get("typ") == "homework":
				continue

			title = item.get("user_meno")

			data = json.loads(item.get("data"))

			if data == None:
				print(item)

			due_date = data.get("date")

			groups = data.get("skupiny")
			description = data.get("nazov")

			event_id = data.get("superid")

			class_name = ids.id_to_class(data.get("triedaid"))

			subject = ids.id_to_subject(data.get("predmetid"))

			timestamp = item.get("timestamp")

			current_homework = EduHomework(due_date, subject, groups, title, description, event_id, class_name, timestamp)
			homework.append(current_homework)
		
		return homework

	def get_news(self):
		if not self.is_logged_in:
			return None
		
		items = self.data.get("items")
		if items == None:
			return None
		
		news = []
		for item in items:
			if not item.get("typ") == "news":
				continue

			text = item.get("text")
			timestamp = item.get("timestamp")
			author = item.get("vlastnik_meno")
			recipient = item.get("user_meno")

			news_message = EduNews(text, timestamp, author, recipient)
			news.append(news_message)
		
		return news

	# this method will soon be removed
	# because all messages will be
	# handled in some other way
	"""
	def get_grade_messages(self):
		if not self.is_logged_in:
			return None
		
		items = self.data.get("items")
		if items == None:
			return None

		ids = IdUtil(self.data)

		messages = []
		for item in items:
			if not item.get("typ") == "znamka":
				continue

			timestamp = item.get("timestamp")
			teacher = item.get("vlastnik_meno")
			text = item.get("text")

			data = json.loads(item.get("data"))
			subject_id = list(data.keys())[0]

			subject = ids.id_to_subject(subject_id)

			grade_data = data.get(subject_id)[0]
			
			grade_id = grade_data.get("znamkaid")
			grade = grade_data.get("data")
			action = grade_data.get("akcia")

			edugrade = EduGradeMessage(teacher, text, subject, grade, action, grade_id, timestamp)
			messages.append(edugrade)
		
		return messages
	"""
	
	def get_grade_data(self):
		response = self.session.get(f"https://{self.school}.edupage.org/znamky")
		
		return json.loads(response.content.decode() \
									.split(".znamkyStudentViewer(")[1] \
									.split(");\r\n\t\t});\r\n\t\t</script>")[0])

	def get_received_grade_events(self):
		grade_data = self.get_grade_data()

		util = GradeUtil(grade_data)
		id_util = IdUtil(self.data)

		received_grade_events = []

		providers = grade_data.get("vsetkyUdalosti")
		events = providers.get("edupage")
		for event_id in events:
			event = events.get(event_id)

			if event.get("stav") == None:
				continue

			name = event.get("p_meno")
			average = event.get("priemer")
			timestamp = event.get("timestamp")

			weight = event.get("p_vaha")

			teacher_id = event.get("UcitelID")
			teacher = util.id_to_teacher(teacher_id)

			subject_id = event.get()
			subject = id_util.id_to_subject(subject_id)

			event = EduGradeEvent(teacher, name, subject, average, weight, timestamp)
			received_grade_events.append(event)
		
		return received_grade_events
	
	def get_students(self):
		try:
			students = self.data.get("dbi").get("students")
		except Exception as e:
			print(e)
			return None
		if students == None:
			return []
		
		result = []
		for student_id in students:
			student_data = students.get(student_id)
			gender = student_data.get("gender")
			firstname = student_data.get("firstname")
			lastname = student_data.get("lastname")
			is_out = student_data.get("isOut")
			number_in_class = student_data.get("numberinclass")


			student = EduStudent(gender, firstname, lastname, student_id, number_in_class, is_out)
			result.append(student)
		return result

"""
TODO:
	- All message types
	- a way to wait for new messages/news/grades... listeners?
"""
