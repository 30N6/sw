import sys, os
import pluto_esm_main_thread
import multiprocessing
import traceback

main_thread = []

def main():
  global main_thread

  main_thread = pluto_esm_main_thread.pluto_esm_main_thread()
  main_thread.run()

if __name__ == "__main__":
  try:
    main()
  except KeyboardInterrupt:
    main_thread.shutdown()
  except Exception as e:
    print("Exception: {}".format(e))
    print(traceback.format_exc())

  processes = multiprocessing.active_children()
  for child in processes:
    print("pluto_esm_app: terminating child process {}".format(child))
    child.terminate()

  sys.exit(0)
  #os._exit(0)
