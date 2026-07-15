NEW_BOOKING_SEARCH_QUERY = """
query NewBookingSearch(
  $origin: String!
  $destination: String!
  $outbound: String!
  $inbound: String
  $productFamilies: [String] = ["PUB"]
  $contractCode: String = "EIL_ALL"
  $adult: Int
  $child: Int
  $infant: Int
  $youth: Int
  $senior: Int
  $adults16Plus: Int = 0
  $children4Only: Int = 0
  $children5To11: Int = 0
  $adultsWheelchair: Int = 0
  $childrenWheelchair: Int = 0
  $guideDogs: Int = 0
  $wheelchairCompanions: Int = 0
  $nonWheelchairCompanions: Int = 0
  $filteredClassesOfService: [ClassOfServiceEnum]
  $filteredClassesOfAccommodation: [ClassEnum]
  $currency: Currency!
  $isAftersales: Boolean = false
  $multipleFlexibility: Boolean = true
  $subscriptionCode: TravelPassTemplateCode
  $showAllSummatedFares: Boolean = false
  $seniorsAges: [Int!]
  $childAges: [Int!]
  $youthAges: [Int!]
  $prioritiseShortHaulODTrains: Boolean = false
  $hideExternalCarrierTrains: Boolean = true
  $hideDirectExternalCarrierTrains: Boolean = true
  $maxTransfers: Int
) {
  journeySearch(
    outboundDate: $outbound
    inboundDate: $inbound
    origin: $origin
    destination: $destination
    adults: $adult
    seniors: $senior
    productFamilies: $productFamilies
    contractCode: $contractCode
    adults16Plus: $adults16Plus
    children: $child
    youths: $youth
    children4Only: $children4Only
    children5To11: $children5To11
    infants: $infant
    adultsWheelchair: $adultsWheelchair
    childrenWheelchair: $childrenWheelchair
    guideDogs: $guideDogs
    wheelchairCompanions: $wheelchairCompanions
    nonWheelchairCompanions: $nonWheelchairCompanions
    isAftersales: $isAftersales
    currency: $currency
    multipleFlexibility: $multipleFlexibility
    subscriptionCode: $subscriptionCode
    showAllSummatedFares: $showAllSummatedFares
    seniorsAges: $seniorsAges
    childAges: $childAges
    youthAges: $youthAges
    prioritiseShortHaulODTrains: $prioritiseShortHaulODTrains
    maxTransfers: $maxTransfers
  ) {
    outbound {
      ...searchBound
    }
  }
}

fragment searchBound on Offer {
  journeys(
    hideIndirectTrainsWhenDisruptedAndCancelled: false
    hideDepartedTrains: true
    hideExternalCarrierTrains: $hideExternalCarrierTrains
    hideDirectExternalCarrierTrains: $hideDirectExternalCarrierTrains
  ) {
    ...journey
  }
}

fragment journey on Journey {
  timing {
    date
    departureTime: departs
    arrivalTime: arrives
  }
  fares(
    filteredClassesOfService: $filteredClassesOfService
    filteredClassesOfAccommodation: $filteredClassesOfAccommodation
  ) {
    classOfService {
      name
      code
    }
    prices {
      displayPrice
      total
      bundlePrice
    }
    seats
    availabilityOfClassOfService
    legs {
      products {
        price
        passengerAgeGroup {
          name
        }
      }
      serviceName
      serviceType {
        code
        brandCode
      }
    }
  }
}
""".strip()
