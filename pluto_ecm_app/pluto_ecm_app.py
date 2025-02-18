import sys, os
import pluto_ecm_main_thread
import multiprocessing
import traceback

main_thread = []

def main():
  global main_thread

  main_thread = pluto_ecm_main_thread.pluto_ecm_main_thread()
  main_thread.run()

if __name__ == "__main__":
  try:
    main()
  except KeyboardInterrupt:
    main_thread.shutdown(True)
  except Exception as e:
    main_thread.shutdown(True)
    print("Exception: {}".format(e))
    print(traceback.format_exc())

  processes = multiprocessing.active_children()
  for child in processes:
    print("pluto_ecm_app: terminating child process {}".format(child))
    child.terminate()

  sys.exit(0)
  #os._exit(0)
