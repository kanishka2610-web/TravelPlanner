import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TripDetailsPage from "./TripDetailsPage.jsx";
import { getActivities, getTrip } from "../services/api.js";

vi.mock("../services/api.js");

const nyTrip = {
  id: 1,
  name: "New York Trip",
  destination: "New York",
  start_date: "2026-11-10",
  end_date: "2026-11-14",
  budget: 50000,
  timezone: "America/New_York",
  status: "upcoming",
  description: "Visiting NYC",
};

function renderPage(tripId = "1") {
  render(
    <MemoryRouter initialEntries={[`/trips/${tripId}`]}>
      <Routes>
        <Route path="/trips/:id" element={<TripDetailsPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("TripDetailsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("displays the trip details including timezone", async () => {
    getTrip.mockResolvedValue(nyTrip);
    getActivities.mockResolvedValue([]);
    renderPage("1");

    expect(await screen.findByText("New York Trip")).toBeInTheDocument();
    expect(screen.getByText("New York")).toBeInTheDocument();
    expect(screen.getByText("Timezone")).toBeInTheDocument();
    expect(screen.getByText("America/New_York")).toBeInTheDocument();
  });

  it("defaults to UTC if timezone is not specified", async () => {
    const tripWithoutTz = { ...nyTrip, timezone: undefined };
    getTrip.mockResolvedValue(tripWithoutTz);
    getActivities.mockResolvedValue([]);
    renderPage("1");

    expect(await screen.findByText("New York Trip")).toBeInTheDocument();
    expect(screen.getByText("Timezone")).toBeInTheDocument();
    expect(screen.getByText("UTC")).toBeInTheDocument();
  });
});

