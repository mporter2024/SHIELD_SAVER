from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

training_data = [

# =========================
# GREETING 
# =========================
("hello", "greeting"),
("hi", "greeting"),
("hey", "greeting"),
("good morning", "greeting"),
("good afternoon", "greeting"),
("what's up", "greeting"),
("how are you", "greeting"),
("yo", "greeting"),
("hi there", "greeting"),
("hello there", "greeting"),
("hey assistant", "greeting"),
("what's going on", "greeting"),
("hey bot", "greeting"),
("sup", "greeting"),
("hi assistant", "greeting"),
("greetings", "greeting"),
("hey what's up", "greeting"),
("hello again", "greeting"),
("hi how are you", "greeting"),
("hey there", "greeting"),

# =========================
# EVENT CREATION 
# =========================
("i want to plan an event", "event_creation"),
("help me organize an event", "event_creation"),
("create an event", "event_creation"),
("how do i plan an event", "event_creation"),
("how do i start planning", "event_creation"),
("help me set up an event", "event_creation"),
("what do i need to plan an event", "event_creation"),
("how do i organize a fundraiser", "event_creation"),
("how do i plan a school event", "event_creation"),
("what are the steps to plan an event", "event_creation"),
("how do i create an event plan", "event_creation"),
("how do i organize everything", "event_creation"),
("how do i get started with an event", "event_creation"),
("help me plan a party", "event_creation"),
("how do i plan a big event", "event_creation"),
("what should i do first when planning an event", "event_creation"),
("how do i organize a campus event", "event_creation"),
("what do i need for event planning", "event_creation"),
("help me plan something", "event_creation"),
("how do i start an event", "event_creation"),

# =========================
# EVENT HELP 
# =========================
("how do i choose a venue", "event_help"),
("help me find a venue", "event_help"),
("how do i plan a timeline", "event_help"),
("how do i organize tasks", "event_help"),
("what should i prepare for an event", "event_help"),
("help me with logistics", "event_help"),
("how should i plan catering", "event_help"),
("how do i manage vendors", "event_help"),
("what should i consider for a venue", "event_help"),
("how do i handle event logistics", "event_help"),
("what should i do for event setup", "event_help"),
("how do i plan event details", "event_help"),
("how do i organize an event schedule", "event_help"),
("what do i need for event logistics", "event_help"),
("how do i plan food for an event", "event_help"),
("how do i organize everything for an event", "event_help"),
("what are the important parts of an event", "event_help"),
("how do i handle event planning details", "event_help"),
("how do i plan an event timeline", "event_help"),
("how do i choose vendors", "event_help"),
("how do i plan event setup", "event_help"),
("what do i need for catering", "event_help"),
("how do i plan decorations", "event_help"),
("how do i organize event flow", "event_help"),
("what should i think about for events", "event_help"),

# =========================
# BUDGETING 
# =========================
("how much does an event cost", "budgeting"),
("help me make a budget", "budgeting"),
("estimate event expenses", "budgeting"),
("how much should i spend on food", "budgeting"),
("how much will catering cost", "budgeting"),
("what should my budget be", "budgeting"),
("how expensive is an event", "budgeting"),
("help me budget my event", "budgeting"),
("what is a good event budget", "budgeting"),
("how do i calculate event cost", "budgeting"),
("how much should i spend", "budgeting"),
("what are typical event costs", "budgeting"),
("estimate cost for fundraiser", "budgeting"),
("how do i budget a school event", "budgeting"),
("how much does a venue cost", "budgeting"),
("what should i budget for food", "budgeting"),
("how do i break down event costs", "budgeting"),
("how do i plan a cheap event", "budgeting"),
("how do i save money on events", "budgeting"),
("what costs should i expect", "budgeting"),
("how do i manage event expenses", "budgeting"),
("how do i reduce event costs", "budgeting"),
("how do i estimate costs", "budgeting"),
("what is a reasonable budget", "budgeting"),
("how do i plan costs for my event", "budgeting"),

# =========================
# TASK HELP 
# =========================
("what should i do next", "task_help"),
("what is my next step", "task_help"),
("show my tasks", "task_help"),
("what tasks are pending", "task_help"),
("what still needs to be done", "task_help"),
("what is left to do", "task_help"),
("what should i work on next", "task_help"),
("what tasks do i have", "task_help"),
("what should i focus on", "task_help"),
("what tasks are incomplete", "task_help"),
("what do i need to finish", "task_help"),
("what are my next tasks", "task_help"),
("what should i complete next", "task_help"),
("what tasks are left", "task_help"),
("help me with tasks", "task_help"),
("what should i prioritize", "task_help"),
("what do i need to do for my event", "task_help"),
("what tasks should i do first", "task_help"),
("what is pending", "task_help"),
("what tasks remain", "task_help"),
("show incomplete tasks", "task_help"),
("what do i need to finish for my event", "task_help"),
("what tasks are coming up", "task_help"),
("what should i work on now", "task_help"),
("what tasks are due soon", "task_help"),

# =========================
# EVENT SUMMARY 
# =========================
("summarize my event", "event_summary"),
("what is the status of my event", "event_summary"),
("give me an event summary", "event_summary"),
("show me the event overview", "event_summary"),
("how is my event looking", "event_summary"),
("what is going on with my event", "event_summary"),
("tell me about my event", "event_summary"),
("give me details about my event", "event_summary"),
("how is my event doing", "event_summary"),
("show event status", "event_summary"),
("what is happening with my event", "event_summary"),
("give me event info", "event_summary"),
("what is my event progress", "event_summary"),
("how far along is my event", "event_summary"),
("what does my event look like", "event_summary"),
("give me a quick summary", "event_summary"),
("event summary please", "event_summary"),
("show me event details", "event_summary"),
("what is my event situation", "event_summary"),
("overview of my event", "event_summary"),
]

texts = [x[0] for x in training_data]
labels = [x[1] for x in training_data]

vectorizer = TfidfVectorizer(ngram_range=(1, 2))
X_train = vectorizer.fit_transform(texts)

model = LogisticRegression(max_iter=1000)
model.fit(X_train, labels)


def detect_intent(text):
    X_input = vectorizer.transform([text])
    
    return model.predict(X_input)[0]


def detect_intent_with_confidence(text):
    X_input = vectorizer.transform([text])
    probabilities = model.predict_proba(X_input)[0]
    classes = model.classes_

    best_index = probabilities.argmax()
    return classes[best_index], float(probabilities[best_index])