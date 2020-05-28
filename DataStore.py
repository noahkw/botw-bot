import concurrent
from abc import ABC, abstractmethod
from functools import partial

import firebase_admin
from firebase_admin import credentials, firestore


class DataStore(ABC):
    def __init__(self):
        pass

    @abstractmethod
    async def set(self, collection, document, val):
        pass

    @abstractmethod
    async def set_get_id(self, collection, val):
        pass

    @abstractmethod
    async def update(self, collection, document, val):
        pass

    @abstractmethod
    async def add(self, collection, val):
        pass

    @abstractmethod
    async def get(self, collection, document):
        pass

    @abstractmethod
    async def delete(self, collection, document):
        pass


class FirebaseDataStore(DataStore):
    def __init__(self, key_file, db_name, loop):
        super().__init__()
        cred = credentials.Certificate(key_file)

        firebase_admin.initialize_app(
            cred, {'databaseURL': f'https://{db_name}.firebaseio.com'})

        self.db = firestore.client()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        self.loop = loop

    async def set(self, collection, document, val):
        ref = self._get_doc_ref(collection, document)
        await self.loop.run_in_executor(self.executor, partial(ref.set, val))

    async def set_get_id(self, collection, val):
        ref = self._get_doc_ref(collection, None)
        await self.loop.run_in_executor(self.executor, partial(ref.set, val))
        return ref.id

    async def update(self, collection, document, val):
        ref = self._get_doc_ref(collection, document)
        await self.loop.run_in_executor(self.executor,
                                        partial(ref.update, val))

    async def add(self, collection, val):
        ref = self._get_collection(collection)
        await self.loop.run_in_executor(self.executor, partial(ref.add, val))

    async def get(self, collection, document=None):
        if document is None:
            ref = self._get_collection(collection)
            return await self.loop.run_in_executor(self.executor, ref.stream)
        else:
            ref = self._get_doc_ref(collection, document)
            return await self.loop.run_in_executor(self.executor, ref.get)

    async def delete(self, collection, document=None):
        if document is not None:
            ref = self._get_doc_ref(collection, document)
            await self.loop.run_in_executor(self.executor, ref.delete)
        else:
            # implement batching later
            docs = self._get_collection(collection).stream()
            for doc in docs:
                await self.loop.run_in_executor(self.executor,
                                                doc.reference.delete)

    async def query(self, collection, *query):
        ref = self._get_collection(collection).where(*query)
        return await self.loop.run_in_executor(self.executor, ref.stream)

    def _get_doc_ref(self, collection, document):
        return self._get_collection(collection).document(document)

    def _get_collection(self, collection):
        return self.db.collection(collection)


if __name__ == '__main__':
    import configparser

    config = configparser.ConfigParser()
    config.read('conf.ini')

    firebase_ds = FirebaseDataStore(config['firebase']['key_file'],
                                    config['firebase']['db_name'])
    firebase_ds.add('jobs', {
        'func': 'somefunc',
        'time': 234903284,
        'args': ['arg1', 'arg2']
    })
