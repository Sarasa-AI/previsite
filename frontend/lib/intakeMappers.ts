import type { Demographics } from "./intake";
import type { DemographicsFormData } from "../src/schemas/demographics";

// Map frontend form data to backend DemographicsInput
export function mapDemographicsToBackend(data: DemographicsFormData | Demographics): Demographics {
  return {
    first_name: data.first_name,
    last_name: data.last_name,
    national_id: data.national_id,
    insurance_provider: data.insurance_provider,
    age: data.age,
    sex: (data.sex === "مرد" ? "male" : data.sex === "زن" ? "female" : data.sex) as "male" | "female",
    weight: data.weight,
    height: data.height,
    chief_complaint: data.chief_complaint,
  };
}

// Map backend Demographics to frontend form data
export function mapDemographicsFromBackend(data: Demographics): DemographicsFormData {
  return {
    first_name: data.first_name,
    last_name: data.last_name,
    national_id: data.national_id,
    insurance_provider: data.insurance_provider,
    age: data.age,
    sex: (data.sex === "مرد" ? "male" : data.sex === "زن" ? "female" : data.sex) as "male" | "female",
    weight: data.weight,
    height: data.height,
    chief_complaint: data.chief_complaint,
  };
}
