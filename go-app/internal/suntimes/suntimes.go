// Package suntimes provides sunrise/sunset calculation for dark mode support.
package suntimes

import (
	"math"
	"time"
)

// Hardcoded coordinates (Washington D.C. area)
const (
	latitude  = 39.003
	longitude = -77.0425
)

// calculateSunTimes calculates sunrise and sunset times for a given date.
// Uses the NOAA solar calculator algorithm (simplified).
// Returns (sunrise, sunset) as UTC times.
func calculateSunTimes(date time.Time) (time.Time, time.Time) {
	// Day of year
	dayOfYear := date.YearDay()

	// Convert latitude to radians
	latRad := latitude * math.Pi / 180

	// Calculate solar declination (approximate)
	declination := 23.45 * math.Sin(2*math.Pi/365*float64(dayOfYear-81))
	declRad := declination * math.Pi / 180

	// Calculate hour angle for sunrise/sunset
	// cos(hour_angle) = -tan(lat) * tan(decl)
	cosHourAngle := -math.Tan(latRad) * math.Tan(declRad)

	// Clamp to valid range (handles polar day/night)
	if cosHourAngle < -1 {
		cosHourAngle = -1
	}
	if cosHourAngle > 1 {
		cosHourAngle = 1
	}

	hourAngle := math.Acos(cosHourAngle) * 180 / math.Pi

	// Solar noon in hours (approximate, based on longitude)
	// Each 15 degrees of longitude = 1 hour offset from UTC
	solarNoonUTC := 12 - (longitude / 15)

	// Sunrise and sunset times in hours UTC
	sunriseHour := solarNoonUTC - (hourAngle / 15)
	sunsetHour := solarNoonUTC + (hourAngle / 15)

	// Convert to time
	baseDate := time.Date(date.Year(), date.Month(), date.Day(), 0, 0, 0, 0, time.UTC)

	sunriseMinutes := int(sunriseHour * 60)
	sunsetMinutes := int(sunsetHour * 60)

	sunrise := baseDate.Add(time.Duration(sunriseMinutes) * time.Minute)
	sunset := baseDate.Add(time.Duration(sunsetMinutes) * time.Minute)

	return sunrise, sunset
}

// IsDarkMode determines if dark mode should be enabled based on current time.
// Returns true if current time is before sunrise or after sunset.
func IsDarkMode() bool {
	now := time.Now().UTC()
	sunrise, sunset := calculateSunTimes(now)
	return now.Before(sunrise) || now.After(sunset)
}
