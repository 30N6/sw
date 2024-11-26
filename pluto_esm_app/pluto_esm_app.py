import sys
import pluto_esm_main_thread

def main():
  main_thread = pluto_esm_main_thread.pluto_esm_main_thread()

  main_thread.run()
  #while True:
  #  reader.read()
  #  #time.sleep(0)

if __name__ == "__main__":
  try:
    main()
  except KeyboardInterrupt:
    sys.exit(0)
