import firebase_admin
from firebase_admin import credentials

# Initialize Firebase Admin SDK with the appropriate service account key and database URL
cred = credentials.Certificate('attendez-bd239-firebase-adminsdk-2nfvi-7bb07f3b17.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://attendez-bd239-default-rtdb.firebaseio.com/'
})
