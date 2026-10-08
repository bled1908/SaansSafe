import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { isNoticeResponse } from "../api/client";
import { makeAqiResponse, makeForecastResponse, makeNoticeResponse } from "../test/fixtures";
import { ParentNotice } from "./ParentNotice";

const COORDS = { lat: 28.6129, lon: 77.2295 };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

function stubFetch(...responses: (() => Response | Promise<Response>)[]) {
  const fetchMock = vi.fn((_url: string, _init?: RequestInit) => {
    const next = responses.length > 1 ? responses.shift()! : responses[0]!;
    return Promise.resolve(next());
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function sentBody(fetchMock: ReturnType<typeof stubFetch>, call = 0) {
  const [url, init] = fetchMock.mock.calls[call]!;
  return { url, method: init?.method, body: JSON.parse(String(init?.body)) };
}

function renderNotice() {
  return render(<ParentNotice coords={COORDS} decision={makeAqiResponse().decision} />);
}

const generateButton = () => screen.getByRole("button", { name: /generate notice/i });

const setNavigator = (key: "clipboard" | "share", value: unknown) =>
  Object.defineProperty(navigator, key, { value, configurable: true, writable: true });

afterEach(() => {
  setNavigator("share", undefined);
  document.querySelectorAll('link[data-font="noto-sans-devanagari"]').forEach((link) => link.remove());
});

describe("ParentNotice", () => {
  it("explains the verified decision and does not call the API until asked", () => {
    const fetchMock = stubFetch(() => json(makeNoticeResponse()));
    renderNotice();
    expect(screen.getByRole("heading", { name: "Parent notice" })).toBeInTheDocument();
    expect(
      screen.getByText("Turn today's verified safety decision into a message parents can understand."),
    ).toBeInTheDocument();
    expect(screen.getByText("Move assembly, PE and sports indoors")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("generates an English notice and shows title, body, key points, footer and sign-off", async () => {
    const fetchMock = stubFetch(() => json(makeNoticeResponse()));
    renderNotice();
    await userEvent.click(generateButton());

    const bubble = await screen.findByTestId("notice-bubble");
    expect(sentBody(fetchMock)).toEqual({
      url: expect.stringMatching(/\/notice$/),
      method: "POST",
      body: { lat: 28.6129, lon: 77.2295, language: "en" },
    });
    expect(within(bubble).getByText("Air quality update for parents · Thu 8 Oct")).toBeInTheDocument();
    expect(within(bubble).getByText(/hold assembly indoors and move PE and sports indoors/)).toBeInTheDocument();
    expect(within(bubble).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "Morning assembly: indoors",
      "PE and sports: indoors",
      "Recess and breaks: shorter outdoors, with an indoor option",
    ]);
    expect(within(bubble).getByText(/May cause breathing discomfort/)).toBeInTheDocument();
    expect(within(bubble).getByText(/This is not medical advice\./)).toBeInTheDocument();
    expect(within(bubble).getByText("— School administration")).toBeInTheDocument();
    expect(bubble).toHaveAttribute("lang", "en");
  });

  it("generates a Hindi notice in Devanagari with the full Hindi font", async () => {
    const hindi = makeNoticeResponse({
      language: "hi",
      notice: {
        title: "अभिभावकों के लिए वायु गुणवत्ता सूचना · गुरुवार, 8 अक्टूबर",
        body: "प्रिय अभिभावकगण, विद्यालय के आसपास वायु गुणवत्ता का पूर्वानुमान/मॉडल अनुमान AQI 242 है।",
        key_points: ["सुबह की प्रार्थना सभा: भवन के अंदर"],
        sign_off: "— विद्यालय प्रशासन",
      },
    });
    const fetchMock = stubFetch(() => json(hindi));
    renderNotice();
    const toggle = screen.getByRole("radio", { name: "हिंदी" });
    await userEvent.click(toggle);
    expect(toggle).toBeChecked();
    expect(document.querySelector('link[data-font="noto-sans-devanagari"]')).not.toBeNull();
    await userEvent.click(generateButton());

    const bubble = await screen.findByTestId("notice-bubble");
    expect(sentBody(fetchMock).body.language).toBe("hi");
    expect(bubble).toHaveAttribute("lang", "hi");
    expect(bubble).toHaveClass("font-deva");
    expect(within(bubble).getByText("— विद्यालय प्रशासन")).toBeInTheDocument();
  });

  it("has a keyboard-accessible language toggle", async () => {
    stubFetch(() => json(makeNoticeResponse()));
    renderNotice();
    screen.getByRole("radio", { name: "English" }).focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("radio", { name: "हिंदी" })).toBeChecked();
  });

  it("regenerates in the new language when the language changes after a notice", async () => {
    const fetchMock = stubFetch(
      () => json(makeNoticeResponse()),
      () => json(makeNoticeResponse({ language: "hi" })),
    );
    renderNotice();
    await userEvent.click(generateButton());
    await screen.findByTestId("notice-bubble");
    await userEvent.click(screen.getByRole("radio", { name: "हिंदी" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(sentBody(fetchMock, 1).body.language).toBe("hi");
  });

  it("sends the optional school name, trimmed", async () => {
    const fetchMock = stubFetch(() => json(makeNoticeResponse({ school_name: "St. Mary's School" })));
    renderNotice();
    await userEvent.type(screen.getByLabelText(/school name/i), "  St. Mary's School  ");
    await userEvent.click(generateButton());
    await screen.findByTestId("notice-bubble");
    expect(sentBody(fetchMock).body).toEqual({ ...COORDS, language: "en", school_name: "St. Mary's School" });
    expect(screen.getByLabelText(/school name/i)).toHaveAttribute("maxLength", "60");
  });

  it("shows a skeleton and disables the controls while writing", async () => {
    stubFetch(() => new Promise<Response>(() => {}));
    renderNotice();
    await userEvent.click(generateButton());
    expect(screen.getByTestId("notice-skeleton")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /writing notice/i })).toBeDisabled();
    expect(screen.getByRole("radio", { name: "हिंदी" })).toBeDisabled();
    expect(screen.getByLabelText(/school name/i)).toBeDisabled();
    expect(document.querySelector("[aria-busy=true]")).not.toBeNull();
  });

  it("shows a calm error with retry, and keeps the decision unaffected", async () => {
    const fetchMock = stubFetch(
      () => json({ error: { code: "upstream_unavailable", message: "Try again shortly." } }, 503),
      () => json(makeNoticeResponse()),
    );
    renderNotice();
    await userEvent.click(generateButton());
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Air-quality data is temporarily unavailable");
    expect(alert).toHaveTextContent("Today's decision above is unaffected.");
    await userEvent.click(within(alert).getByRole("button", { name: /try again/i }));
    await screen.findByTestId("notice-bubble");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shows the server's school-name message without a pointless retry", async () => {
    stubFetch(() =>
      json({ error: { code: "invalid_school_name", message: "Field 'school_name' may contain only letters." } }, 400),
    );
    renderNotice();
    await userEvent.click(generateButton());
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Check the school name");
    expect(alert).toHaveTextContent("may contain only letters");
    expect(within(alert).queryByRole("button")).toBeNull();
  });

  it("explains when the deployed API has no notice endpoint yet", async () => {
    stubFetch(() => json({ message: "Not Found" }, 404));
    renderNotice();
    await userEvent.click(generateButton());
    expect(await screen.findByRole("alert")).toHaveTextContent("isn't available on this server yet");
  });

  it("presents a template fallback normally, as a verified template", async () => {
    stubFetch(() => json(makeNoticeResponse({ generated_by: "template", fallback_reason: "ai_timeout" })));
    renderNotice();
    await userEvent.click(generateButton());
    await screen.findByTestId("notice-bubble");
    expect(screen.getAllByText("Verified template")).toHaveLength(2); // provenance line + facts
    expect(screen.queryByRole("alert")).toBeNull();
    expect(document.body.textContent).not.toMatch(/ai_timeout|fallback|error/i);
  });

  it("labels a Bedrock-worded notice without implying it made the decision", async () => {
    stubFetch(() =>
      json(makeNoticeResponse({ generated_by: "bedrock", model: "apac.amazon.nova-lite-v1:0", fallback_reason: null })),
    );
    renderNotice();
    await userEvent.click(generateButton());
    await screen.findByTestId("notice-bubble");
    expect(screen.getByText("Worded by Amazon Bedrock")).toBeInTheDocument();
    expect(screen.getByText(/checked against SaansSafe's\s+decision/)).toBeInTheDocument();
  });

  it("copies the API's share text", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    setNavigator("clipboard", { writeText });
    stubFetch(() => json(makeNoticeResponse()));
    renderNotice();
    await user.click(generateButton());
    await user.click(await screen.findByRole("button", { name: "Copy message" }));
    expect(writeText).toHaveBeenCalledWith(makeNoticeResponse().share_text);
    expect(screen.getByRole("status")).toHaveTextContent("Copied.");
  });

  it("falls back to selecting the message when the clipboard is unavailable", async () => {
    const user = userEvent.setup();
    setNavigator("clipboard", undefined);
    stubFetch(() => json(makeNoticeResponse()));
    renderNotice();
    await user.click(generateButton());
    await user.click(await screen.findByRole("button", { name: "Copy message" }));
    expect(screen.getByRole("status")).toHaveTextContent("Couldn't copy automatically");
    expect(window.getSelection()?.toString()).toContain("Air quality update for parents");
  });

  it("without Web Share, Copy is the primary action and no Share button appears", async () => {
    stubFetch(() => json(makeNoticeResponse()));
    renderNotice();
    await userEvent.click(generateButton());
    const copy = await screen.findByRole("button", { name: "Copy message" });
    expect(screen.queryByRole("button", { name: "Share" })).toBeNull();
    expect(copy).toHaveClass("bg-ink");
  });

  it("uses Web Share when the browser has it", async () => {
    const share = vi.fn().mockResolvedValue(undefined);
    setNavigator("share", share);
    stubFetch(() => json(makeNoticeResponse()));
    renderNotice();
    await userEvent.click(generateButton());
    await userEvent.click(await screen.findByRole("button", { name: "Share" }));
    expect(share).toHaveBeenCalledWith({
      title: makeNoticeResponse().notice.title,
      text: makeNoticeResponse().share_text,
    });
  });

  it("prints only the notice copy", async () => {
    let printingNoticeOnly = false;
    const print = vi.spyOn(window, "print").mockImplementation(() => {
      printingNoticeOnly = document.body.classList.contains("print-notice");
    });
    stubFetch(() => json(makeNoticeResponse()));
    renderNotice();
    await userEvent.click(generateButton());
    await userEvent.click(await screen.findByRole("button", { name: "Print notice" }));
    expect(print).toHaveBeenCalledOnce();
    expect(printingNoticeOnly).toBe(true);
    expect(document.querySelector("body > [data-print-notice]")).toHaveTextContent("Air quality update for parents");
    window.dispatchEvent(new Event("afterprint"));
    expect(document.body).not.toHaveClass("print-notice");
  });

  it("shows the API's facts exactly, without recalculating anything in the browser", async () => {
    // Deliberately inconsistent with the decision prop: the UI must echo the response, not "fix" it.
    const base = makeNoticeResponse();
    const odd = makeNoticeResponse({
      grounding: { ...base.grounding, aqi_display: "10", category: "Severe" },
      decision: { ...base.decision, headline: "Suspend all outdoor activities" },
    });
    stubFetch(() => json(odd));
    renderNotice();
    await userEvent.click(generateButton());
    await screen.findByTestId("notice-bubble");
    const facts = screen.getByText("Facts used").closest("details")!;
    expect(within(facts).getByText("10 · Severe")).toBeInTheDocument();
    expect(within(facts).getByText("Suspend all outdoor activities")).toBeInTheDocument();
    expect(facts).toHaveTextContent(/4:30–5:30 pm IST/);
    expect(document.body.textContent).not.toContain("CPCB AQI");
  });
});

describe("Create parent notice CTA", () => {
  it("scrolls to and focuses the parent notice section, keeping the decision primary", async () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(json(String(url).includes("/forecast?") ? makeForecastResponse() : makeAqiResponse())),
      ),
    );
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Delhi/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Create parent notice" }));
    expect(scrollIntoView).toHaveBeenCalledWith(expect.objectContaining({ block: "start" }));
    expect(screen.getByRole("heading", { name: "Parent notice" })).toHaveFocus();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Move assembly, PE and sports indoors.");
  });
});

describe("isNoticeResponse", () => {
  it("accepts the notice contract and rejects other shapes", () => {
    expect(isNoticeResponse(makeNoticeResponse())).toBe(true);
    expect(isNoticeResponse({ ...makeNoticeResponse(), language: "fr" })).toBe(false);
    expect(isNoticeResponse({ ...makeNoticeResponse(), notice: { title: "x" } })).toBe(false);
    expect(isNoticeResponse(makeAqiResponse())).toBe(false);
  });
});
