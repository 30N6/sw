import sys, os
import pluto_esm_main_thread

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
    #sys.exit(0)
    os._exit(0)
