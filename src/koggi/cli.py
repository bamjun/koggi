import sys

def main():
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == 'helloworld':
            print('helloworld')
        elif command == 'koggi':
            print('koggi')
        else:
            print(f"Unknown command: {command}")
    else:
        print("Usage: koggi [helloworld|koggi]")

if __name__ == '__main__':
    main()