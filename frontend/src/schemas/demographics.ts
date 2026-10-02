import { z } from "zod";
import { validateIranianNationalId } from "@/lib/national-id";

export const demographicsSchema = z.object({
  first_name: z.string().min(1, "نام الزامی است"),
  last_name: z.string().min(1, "نام خانوادگی الزامی است"),
  national_id: z
    .string()
    .length(10, "کد ملی باید دقیقاً ۱۰ رقم باشد")
    .regex(/^\d+$/, "کد ملی باید فقط شامل اعداد باشد")
    .refine(validateIranianNationalId, "کد ملی وارد شده معتبر نیست"),
  insurance_provider: z.string().min(1, "بیمه الزامی است"),
  age: z
    .number()
    .int("سن باید یک عدد صحیح باشد")
    .min(0, "سن نمی‌تواند منفی باشد")
    .max(150, "سن باید حداکثر ۱۵۰ باشد"),
  sex: z.enum(["male", "female"]),
  weight: z.number().positive("وزن باید مثبت باشد"),
  height: z.number().positive("قد باید مثبت باشد"),
  chief_complaint: z.string().min(1, "شکایت اصلی الزامی است"),
});

export type DemographicsFormData = z.infer<typeof demographicsSchema>;
