import threading
import time


def exampleA():
    print("test start A")
    a=1
    time.sleep(3)
    return a

def exampleB():
    print("test start B")
    a=2
    time.sleep(1)
    return a

myFunc = [exampleA, exampleB]

def publish_thread():

    results = []
    for callback in myFunc:
        thread = threading.Thread(
            target=lambda cb=callback: results.append(cb())
        )
        thread.start()
        thread.join()  # Wait for thread to finish
        #return results[0] if results else None  # Return first result

    return results

def publish_thread_2():

    results = [None]*len(myFunc)
    threads = []
    for idx, callback in enumerate(myFunc):
        thread = threading.Thread(
            target=lambda cb=callback, i=idx: results.__setitem__(i, cb())
        )
        threads.append(thread)
        thread.start()
    for t in threads:
        t.join() #If a thread has already end, join will do nothing nor raise error
    return results

def publish_call():

    results = []
    for cb in myFunc:
        results.append(cb())

    return results

# start = time.time()
# print("Start thread")
# c = publish_thread()
# print(c)
# end = time.time()
# print(f"Took f{end-start}s")

start = time.time()
print("Start call")
c = publish_call()
print(c)
end = time.time()
print(f"Call Took f{end-start}s")

start = time.time()
print("Start thread")
c = publish_thread_2()
print(c)
end = time.time()
print(f"thread Took f{end-start}s")
