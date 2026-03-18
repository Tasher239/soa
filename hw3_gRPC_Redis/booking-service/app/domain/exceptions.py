class BookingNotFoundError(Exception):
    def __init__(self, booking_id: str):
        self.booking_id = booking_id
        super().__init__(f"Booking {booking_id} not found")


class BookingAlreadyCancelledError(Exception):
    def __init__(self, booking_id: str):
        self.booking_id = booking_id
        super().__init__(f"Booking {booking_id} is already cancelled")


class FlightNotFoundError(Exception):
    def __init__(self, flight_id: int):
        self.flight_id = flight_id
        super().__init__(f"Flight {flight_id} not found")


class NoSeatsAvailableError(Exception):
    def __init__(self, flight_id: int):
        self.flight_id = flight_id
        super().__init__(f"No seats available on flight {flight_id}")


class ServiceUnavailableError(Exception):
    def __init__(self, message: str = "Flight service unavailable"):
        super().__init__(message)
