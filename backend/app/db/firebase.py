import firebase_admin
from firebase_admin import credentials, firestore
from firebaseAccountKey import info

cred = credentials.Certificate(info)
firebase_admin.initialize_app(cred)
db = firestore.client()