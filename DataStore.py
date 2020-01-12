from abc import ABC, abstractmethod

import firebase_admin
from firebase_admin import credentials, firestore


class DataStore(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def set(self, collection, document, val):
        pass

    @abstractmethod
    def update(self, collection, document, val):
        pass

    @abstractmethod
    def add(self, collection, val):
        pass

    @abstractmethod
    def get(self, collection, document):
        pass

    @abstractmethod
    def delete(self, collection, document):
        pass


class FirebaseDataStore(DataStore):
    def __init__(self, key_file, db_name):
        super().__init__()
        cred = credentials.Certificate(key_file)

        firebase_admin.initialize_app(cred, {
            'databaseURL': f'https://{db_name}.firebaseio.com'
        })

        self.db = firestore.client()

    def set(self, collection, document, val):
        self._get_doc_ref(collection, document).set(val)

    def update(self, collection, document, val):
        self._get_doc_ref(collection, document).update(val)

    def add(self, collection, val):
        self._get_collection(collection).add(val)

    def get(self, collection, document=None):
        return self._get_collection(collection).stream() if document is None else self._get_doc_ref(collection,
                                                                                                    document).get()

    def delete(self, collection, document):
        self._get_doc_ref(collection, document).delete()

    def query(self, collection, *query):
        return self._get_collection(collection).where(*query).stream()

    def _get_doc_ref(self, collection, document):
        return self._get_collection(collection).document(document)

    def _get_collection(self, collection):
        return self.db.collection(collection)


if __name__ == '__main__':
    import configparser

    config = configparser.ConfigParser()
    config.read('conf.ini')

    firebase_ds = FirebaseDataStore(
        config['firebase']['key_file'], config['firebase']['db_name'])
    firebase_ds.add('jobs', {'func': 'somefunc', 'time': 234903284, 'args': ['arg1', 'arg2']})
