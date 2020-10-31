import concurrent
from abc import ABC, abstractmethod

import firebase_admin
from firebase_admin import credentials, firestore


class DataStore(ABC):
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
            cred, {"databaseURL": f"https://{db_name}.firebaseio.com"}
        )

        self.db = firestore.client()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        self.loop = loop

    async def set(self, collection, document, val):
        ref = await self._get_doc_ref(collection, document)
        await self.loop.run_in_executor(self.executor, ref.set, val)

    async def set_get_id(self, collection, val):
        ref = await self._get_doc_ref(collection, None)
        await self.loop.run_in_executor(self.executor, ref.set, val)
        return ref.id

    async def update(self, collection, document, val):
        ref = await self._get_doc_ref(collection, document)
        await self.loop.run_in_executor(self.executor, ref.update, val)

    async def add(self, collection, val):
        ref = await self._get_collection(collection)
        await self.loop.run_in_executor(self.executor, ref.add, val)

    async def get(self, collection, document=None):
        if document is None:
            ref = await self._get_collection(collection)
            return await self.loop.run_in_executor(self.executor, ref.stream)
        else:
            ref = await self._get_doc_ref(collection, document)
            return await self.loop.run_in_executor(self.executor, ref.get)

    async def delete(self, collection, document=None):
        if document is not None:
            ref = await self._get_doc_ref(collection, document)
            await self.loop.run_in_executor(self.executor, ref.delete)
        else:
            # implement batching later
            docs = (await self._get_collection(collection)).stream()
            for doc in docs:
                await self.loop.run_in_executor(self.executor, doc.reference.delete)

    async def query(self, collection, *query):
        ref = (await self._get_collection(collection)).where(*query)
        return await self.loop.run_in_executor(self.executor, ref.stream)

    async def _get_doc_ref(self, collection, document):
        collection = await self._get_collection(collection)
        return await self.loop.run_in_executor(
            self.executor, collection.document, document
        )

    async def _get_collection(self, collection):
        return await self.loop.run_in_executor(
            self.executor, self.db.collection, collection
        )
