import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Examination } from "../../lib/api";
import { PrescriptionPrint } from "./PrescriptionPrint";

describe("printable prescription", () => {
  it("renders identity, measurements, examiner, and a clear draft label", () => {
    const examination = {
      id: "exam-1", tenant_id: "tenant-1", examination_number: "EXM-TEST001", customer_id: "customer-1",
      customer_name: "Nimal Perera", visit_id: "visit-1", examiner_id: "user-1", examiner_name: "Dr. Silva",
      examined_at: "2026-10-23T10:00:00Z", status: "draft", finalized_at: null, supersedes_id: null,
      revision_number: 1, version: 1, created_at: "2026-10-23T10:00:00Z", updated_at: "2026-10-23T10:00:00Z",
      prescription_type: "distance", od_sphere: "-1.25", os_sphere: "-1.00", pd_binocular: "62.00",
    } as Examination;
    const output = renderToStaticMarkup(<PrescriptionPrint examination={examination} />);
    expect(output).toContain("DRAFT — NOT FINAL");
    expect(output).toContain("Nimal Perera");
    expect(output).toContain("-1.25");
    expect(output).toContain("Dr. Silva");
    expect(output).not.toContain("Examiner signature");
  });
});
