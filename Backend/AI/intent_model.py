from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

# Training data (from BOTH bots merged)
texts = [
    "I want to plan an event",
    "help me organize an event",
    "create event",
    "start planning",
    "hello",
    "hi",
    "hey",
    "what's up",
    "how do I choose a venue",
    "how do I plan a timeline",
    "how much does an event cost"
]

labels = [
    "event_creation",
    "event_creation",
    "event_creation",
    "event_creation",
    "greeting",
    "greeting",
    "greeting",
    "greeting",
    "event_help",
    "event_help",
    "budgeting"
]

vectorizer = TfidfVectorizer()
X_train = vectorizer.fit_transform(texts)

model = LogisticRegression()
model.fit(X_train, labels)

def detect_intent(text):
    X_input = vectorizer.transform([text])
    return model.predict(X_input)[0]