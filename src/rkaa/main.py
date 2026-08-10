from rkaa.core.logging import configure_logging


def main() -> None:
    configure_logging()
    print("RKAA installed. Use scripts/run_collection_once.py.")


if __name__ == "__main__":
    main()
