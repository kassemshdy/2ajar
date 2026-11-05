import type { components } from "./schema";

export type { components, paths } from "./schema";

type S = components["schemas"];

export type User = S["UserOut"];
export type Location = S["LocationOut"];
export type ListingPublic = S["ListingPublic"];
export type ListingPrivate = S["ListingPrivate"];
export type ListingCreate = S["ListingCreate"];
export type ListingUpdate = S["ListingUpdate"];
export type Media = S["MediaOut"];
export type LeadCreate = S["LeadCreate"];
export type LeadReceipt = S["LeadReceipt"];
export type LeadWithListing = S["LeadWithListing"];
export type ListingPage = S["Page_ListingPublic_"];
export type Amenity = S["Amenity"];
export type PropertyType = S["PropertyType"];
export type Furnished = S["Furnished"];
export type TransactionType = S["TransactionType"];
export type PricePeriod = S["PricePeriod"];
export type ListingStatus = S["ListingStatus"];

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}
export type ImportResult = S["ImportResultOut"];
export type ImportRow = S["ImportRowOut"];
