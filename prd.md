## App Concept

### **Core Purpose**: 
Campus-wide visibility tool for bike transportation - **NOT** a ride-matching service

### **Target Area**: 
Obafemi Awolowo University (OAU) campus boundaries with geofencing

## Key Features Specification

### 1. **Geofencing & Campus Boundaries**
```javascript
// OAU Campus Boundary Definition
const OAU_BOUNDARIES = {
  // Define polygon coordinates for OAU campus
  center: { lat: 7.5227, lng: 4.5198 }, // Approximate OAU coordinates
  radius: 5000, // 5km radius or custom polygon
  zones: [
    'Main Campus',
    'Student Hostels', 
    'Staff Quarters',
    'Teaching Hospital',
    'Agricultural Farm'
  ]
}
```

### 2. **Legal & Safety Framework**
```markdown
## Prominent Disclaimers (Required on every launch):

⚠️ **SAFETY FIRST**: 
- This app provides location visibility ONLY
- NO ride matching or booking services
- Users are 100% responsible for their safety
- Always verify driver identity and bike condition
- Trust your instincts - if something feels wrong, don't proceed

⚠️ **LIABILITY**: 
- OAU Campus Bike Visibility App provides information only
- Not responsible for any incidents during transportation
- Users participate at their own risk
```

### 3. **Enhanced Safety Features**

#### **Panic/Distress Button**
```javascript
// Emergency Alert System
const emergencyContacts = {
  studentUnion: '+234-xxx-xxx-xxxx',
  campusSecurity: '+234-xxx-xxx-xxxx', 
  oauClinic: '+234-xxx-xxx-xxxx',
  emergencyServices: '199', // Nigeria emergency
  userEmergencyContact: user.emergencyContact
}

// Panic button triggers:
- SMS alerts to all emergency contacts
- Location sharing with authorities
- Automatic call to campus security
- Alert nearby app users (optional)
```

### 4. **Campus-Specific Features**

#### **OAU Location Markers**
- **Academic Buildings**: FUTA, Science Complex, Arts Theatre
- **Hostels**: Mozambique, Angola, Madagascar, etc.
- **Key Landmarks**: Oduduwa Hall, Sports Complex, SUB
- **Gates**: Main Gate, Back Gate, other entry points
- **Popular Spots**: Buka areas, Banks, ATMs

#### **Bike Availability Context**
```javascript
locationContext = {
  bikeAvailability: 'high' | 'medium' | 'low' | 'none',
  lastUpdated: timestamp,
  reportedBy: anonymousUserId,
  commonPickupSpots: ['Main Gate', 'Hostel Junction', 'SUB']
}
```

## Technical Implementation

### **App Architecture**
```
📱 Frontend (React Native/Flutter)
├── Map Component (Google Maps/Mapbox/Leaflet)
├── Emergency Button (Always visible)
├── Role Toggle (Driver/Passenger)
├── Location Reporter
└── Campus Boundary Checker

🔧 Backend (FastAPI/Python)
├── Real-time Location WebSocket
├── Emergency Alert System
├── Campus Geofencing
├── Analytics Collection
└── Ad Serving (Future)

🗄️ Database (PostgreSQL + PostGIS)
├── User Sessions (Temporary)
├── Location History (24hr retention)
├── Emergency Logs
└── Campus Analytics
```

### **Privacy-First Design**
```javascript
// No persistent user data
const sessionData = {
  sessionId: uuid(), // Temporary session only
  role: 'passenger' | 'driver',
  campusVerified: boolean,
  emergencyContact: encrypted_phone,
  activeUntil: timestamp // Auto-expire after 4 hours
}

// Location data auto-purge
const locationRetention = 24; // hours
const analyticsData = aggregateOnly; // No individual tracking
```

## Revenue Model (Future)

### **Campus Business Ads**
- **Local Restaurants**: "Mama Put near Mozambique Hostel"
- **Stationery Shops**: "Cheap printing at SUB"
- **Laundry Services**: "Pick up/delivery available"
- **Tutorial Centers**: "JAMB/Post-UTME prep"
- **Student Services**: Phone repairs, tailoring, etc.

### **Ad Integration**
- Small banner ads (non-intrusive)
- Location-based promotions
- Student discount partnerships

## Development Phases

### **Phase 1 - Core MVP (2-3 months)**
- [x] OAU campus geofencing
- [x] Basic map with driver/passenger visibility
- [x] Emergency panic button
- [x] Disclaimer screens
- [x] Role selection with memory

### **Phase 2 - Safety & Polish (1-2 months)**
- [x] Emergency contact system integration
- [x] Campus landmark markers
- [x] Bike availability reporting
- [x] User session management

### **Phase 3 - Analytics & Revenue (2-3 months)**
- [x] Usage pattern analysis
- [x] Campus business ad platform
- [x] Performance optimization

## Campus Integration Strategy

### **Partnerships to Consider**
1. **Student Union**: Emergency response protocol
2. **Campus Security**: Direct hotline integration  
3. **OAU IT Center**: Potential hosting/support
4. **Student Entrepreneurs**: Local business ads
5. **Campus Media**: Launch promotion

### **Validation & Testing**
- **Beta test** with student volunteers
- **Security team** consultation
- **Legal review** of disclaimers
- **Load testing** during peak hours (class changes)

## Next Steps

1. **Campus Boundary Mapping**: Get exact OAU coordinates/boundaries
2. **Emergency Protocol**: Establish contact with Student Union/Security
3. **Technical Architecture**: Choose tech stack and start development
4. **Legal Documentation**: Draft comprehensive disclaimers
5. **User Research**: Survey students about current transportation pain points