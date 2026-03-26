from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

texts = [
    "I want to plan an event",
    "help me organize an event",
    "create event",
    "start planning an event",
    "how do I get started with an event",
    "hello",
    "hi",
    "hey",
    "good morning",
    "what's up",
    "how do I choose a venue",
    "help me find a venue",
    "how do I plan a timeline",
    "how do I organize tasks for an event",
    "what should I prepare for an event",
    "how much does an event cost",
    "help me make a budget",
    "estimate event expenses",
    "how much should I spend on food",
    "how much will catering cost"
]

labels = [
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
    "event_help",
    "event_help",
    "event_help",
    "event_help",
    "event_help",
    "budgeting",
    "budgeting",
    "budgeting",
    "budgeting",
    "budgeting"
]

vectorizer = TfidfVectorizer(ngram_range=(1, 2))
X_train = vectorizer.fit_transform(texts)

model = LogisticRegression(max_iter=1000)
model.fit(X_train, labels)


def detect_intent(text):
    X_input = vectorizer.transform([text])
    return model.predict(X_input)[0]