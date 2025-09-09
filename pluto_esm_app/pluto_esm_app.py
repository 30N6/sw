import sys, os
import pluto_esm_main_thread
import multiprocessing
import traceback

if __name__ == "__main__":
  main_thread = pluto_esm_main_thread.pluto_esm_main_thread()

  try:
    main_thread.run()

  except KeyboardInterrupt:
    main_thread.shutdown(True)
  except Exception as e:
    main_thread.shutdown(True)
    print("Exception: {}".format(e))
    print(traceback.format_exc())

  processes = multiprocessing.active_children()
  for child in processes:
    print("pluto_esm_app: terminating child process {}".format(child))
    child.terminate()

  sys.exit(0)
  #os._exit(0)
