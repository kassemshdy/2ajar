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
export type AdminUser = S["AdminUserOut"];
export type AdminUserPage = S["Page_AdminUserOut_"];
export type AdminUserUpdate = S["AdminUserUpdate"];
export type PermissionInfo = S["PermissionInfo"];
export type Permission = S["Permission"];
export type UserRole = S["UserRole"];
export type Ticket = S["TicketOut"];
export type TicketSummary = S["TicketSummary"];
export type TicketPage = S["Page_TicketSummary_"];
export type TicketComment = S["CommentOut"];
export type TicketStatus = S["TicketStatus"];
export type TicketPriority = S["TicketPriority"];
export type TicketCategory = S["TicketCategory"];
export type ApiToken = S["ApiTokenOut"];
export type ApiTokenCreated = S["ApiTokenCreated"];
export type AskRequest = S["AskRequest"];
export type AskResponse = S["AskResponse"];
export type AskHit = S["AskHit"];
export type AskReason = S["ReasonOut"];
export type Suggestion = S["Suggestion"];
export type LivingFactors = S["LivingFactorsOut"];
export type AreaProfile = S["AreaProfileOut"];
export type AreaProfileInput = S["AreaProfileIn"];
export type DiscoverOut = S["DiscoverOut"];
export type NearbyListing = S["NearbyListing"];
export type Stay = S["Stay"];
export type GrowthDashboard = S["GrowthOut"];
export type AgencyPage = S["AgencyPage"];
export type AdminAgency = S["AdminAgencyOut"];
export type ListingStats = S["ListingStats"];
