import type { Metadata } from "next";
import HomePage from "../page";

/**
 * The old WordPress site sent "/" to "/home/" with a permanent (301) redirect,
 * which browsers remember. Serving the home page here too means returning
 * visitors still land on it; a redirect back to "/" would loop for them.
 */
export const metadata: Metadata = {
  alternates: { canonical: "/" },
  robots: { index: false, follow: true },
};

export default HomePage;
