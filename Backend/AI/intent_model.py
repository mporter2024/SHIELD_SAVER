from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

texts = [
    # event creation
    "I want to plan an event",
    "help me organize an event",
    "create event",
    "start planning an event",
    "how do I get started with an event",
    "help me plan a school event",
    "how do I set up an event",
    "what do I need to plan an event",

    # greeting
    "hello",
    "hi",
    "hey",
    "good morning",
    "what's up",
    "how are you",

    # event help
    "how do I choose a venue",
    "help me find a venue",
    "how do I plan a timeline",
    "how do I organize tasks for an event",
    "what should I prepare for an event",
    "help me with logistics",
    "how should I plan catering",
    "how do I manage vendors",

    # budgeting
    "how much does an event cost",
    "help me make a budget",
    "estimate event expenses",
    "how much should I spend on food",
    "how much will catering cost",
    "what should my budget be",
    "how expensive will this event be",

    # task help
    "what should I do next",
    "what is my next step",
    "show my tasks",
    "what tasks are pending",
    "what still needs to be done",
    "what is left to do",
    "what should I work on next",

    # event summary
    "summarize my event",
    "what is the status of my event",
    "give me an event summary",
    "show me the event overview",
    "how is my event looking"
]

labels = [
    "event_creation",
    "event_creation",
    "event_creation",
    "event_creation",
    "event_creation",
    "event_creation",
    "event_creation",
    "event_creation",

    "greeting",
    "greeting",
    "greeting",
    "greeting",
    "greeting",
    "greeting",

    "event_help",
    "event_help",
    "event_help",
    "event_help",
    "event_help",
    "event_help",
    "event_help",
    "event_help",

    "budgeting",
    "budgeting",
    "budgeting",
    "budgeting",
    "budgeting",
    "budgeting",
    "budgeting",

    "task_help",
    "task_help",
    "task_help",
    "task_help",
    "task_help",
    "task_help",
    "task_help",

    "event_summary",
    "event_summary",
    "event_summary",
    "event_summary",
    "event_summary"
]

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