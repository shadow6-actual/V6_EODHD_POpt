const pptxgen = require("pptxgenjs");

// Create Presentation
const pptx = new pptxgen();
pptx.layout = "LAYOUT_16x9";

const colors = {
  primary: "FFB703",
  secondary: "219EBC",
  text: "023047",
  white: "FFFFFF",
  surface: "FAF9F6",
  accent: "FB8500"
};

// PRODUCT LIST (from your Jeopardy file)
const items = [
  { name: "Hatch Rest Sound Machine", img: "hatch_rest.jpg" },
  { name: "Hatch Go Portable Sound Machine", img: "hatch_go.jpg" },
  { name: "SNOObear White Noise Plush", img: "snoobear.jpg" },
  { name: "SNOObie 3-in-1 Sleep Device", img: "snoobie.jpg" },
  { name: "SNOO Smart Sleeper Bassinet", img: "snoo.jpg" },

  { name: "Ergobaby Omni Classic Carrier", img: "ergobaby_omni.jpg" },
  { name: "Baby Wrap Carrier", img: "baby_wrap.jpg" },
  { name: "Ergonomic M-Position Carrier", img: "m_position.jpg" },
  { name: "Lumbar Support Accessory", img: "lumbar_support.jpg" },
  { name: "JPMA-Certified Ergobaby Carrier", img: "ergobaby_jpma.jpg" },

  { name: "Graco SnugRide 35 Lite LX", img: "graco_snugride.jpg" },
  { name: "UPPAbaby Mesa Car Seat", img: "uppa_mesa.jpg" },
  { name: "Chicco KeyFit 35", img: "keyfit35.jpg" },
  { name: "UPPAbaby Aria (6.5 lbs)", img: "uppa_aria.jpg" },
  { name: "LATCH Car Seat", img: "latch_car_seat.jpg" },

  { name: "Dr. Brown’s Anti-Colic Bottles", img: "dr_browns.jpg" },
  { name: "Philips Avent Bottle Warmer", img: "avent_warmer.jpg" },
  { name: "Bottle Sterilizer and Dryer", img: "sterilizer_dryer.jpg" },
  { name: "Baby Brezza Formula Pro", img: "formula_pro.jpg" },
  { name: "Hatch Grow Smart Changing Pad", img: "hatch_grow.jpg" },

  { name: "Keekaroo Peanut Changer", img: "keekaroo.jpg" },
  { name: "Gathre Portable Changing Pad", img: "gathre_pad.jpg" },
  { name: "Nursery Diaper Caddy", img: "diaper_caddy.jpg" },
  { name: "Dyson Purifier + Humidifier", img: "dyson.jpg" },
  { name: "Lovevery Play Kit", img: "lovevery.jpg" }
];

// TITLE SLIDE
let titleSlide = pptx.addSlide();
titleSlide.background = { color: colors.primary };
titleSlide.addText("THE PRICE IS RIGHT", {
  x: 0.5, y: 1.3, w: 9, h: 1.3,
  fontSize: 60, color: colors.white, bold: true,
  align: "center", fontFace: "Georgia"
});
titleSlide.addText("Baby Shower Edition (Amazon Baby Registry)", {
  x: 0.5, y: 3.2, w: 9, h: 0.8,
  fontSize: 26, color: colors.surface,
  align: "center", italic: true
});
titleSlide.addText("Press → to Begin", {
  x: 0.5, y: 4.7, w: 9, h: 0.5,
  fontSize: 18, color: colors.white, align: "center"
});

// INSTRUCTIONS SLIDE
let rulesSlide = pptx.addSlide();
rulesSlide.background = { color: colors.surface };
rulesSlide.addText("HOW TO PLAY", {
  x: 0.5, y: 0.4, w: 9, h: 0.7,
  fontSize: 40, color: colors.primary, bold: true
});
rulesSlide.addText(
  [
    { text: "Two teams (4–6 players each)." },
    { text: "Each round, one representative from each team guesses the price." },
    { text: "Closest guess wins (optionally: closest WITHOUT going over)." },
    { text: "Winner earns 100 points for their team." },
    { text: "Play through 15–20 items (~20 minutes)." }
  ],
  { x: 0.5, y: 1.3, w: 9, h: 3.5, fontSize: 26, color: colors.text, bullet: true }
);

// CREATE PRODUCT GUESS SLIDES
items.forEach((item) => {
  // Guess Slide
  let s = pptx.addSlide();
  s.background = { color: colors.surface };

  s.addText(item.name, {
    x: 0.5, y: 0.3, w: 9, h: 0.6,
    fontSize: 34, color: colors.text, bold: true, align: "center"
  });

  s.addImage({
    path: `images/${item.img}`,
    x: 2.5, y: 1.1, w: 5, h: 3.5
  });

  s.addText("What is the price?", {
    x: 0.5, y: 4.8, w: 9, h: 0.6,
    fontSize: 32, color: colors.accent, bold: true, align: "center"
  });

  // Reveal Slide
  let r = pptx.addSlide();
  r.background = { color: colors.primary };
  r.addText("ACTUAL AMAZON PRICE", {
    x: 0.5, y: 1, w: 9, h: 1,
    fontSize: 40, color: colors.white, align: "center"
  });
  r.addText(item.name, {
    x: 0.5, y: 2.2, w: 9, h: 1,
    fontSize: 32, color: colors.secondary, align: "center"
  });
  r.addImage({
    path: `images/${item.img}`,
    x: 2.5, y: 3, w: 5, h: 3.5
  });

  // IMPORTANT: You manually enter prices into these slides after downloading real Amazon prices.
  r.addText("Insert Price Here: $____", {
    x: 0.5, y: 6.6, w: 9, h: 0.6,
    fontSize: 38, color: colors.white, bold: true, align: "center"
  });
});

// FINAL SCORE SLIDE
let scoreSlide = pptx.addSlide();
scoreSlide.background = { color: colors.secondary };
scoreSlide.addText("FINAL SCORES", {
  x: 0.5, y: 1, w: 9, h: 1,
  fontSize: 48, color: colors.white, align: "center", bold: true
});
scoreSlide.addText("Team 1: ____________", {
  x: 1, y: 2.5, w: 8, h: 0.8,
  fontSize: 30, color: colors.white, align: "center"
});
scoreSlide.addText("Team 2: ____________", {
  x: 1, y: 3.5, w: 8, h: 0.8,
  fontSize: 30, color: colors.white, align: "center"
});

// SAVE FILE
pptx.writeFile("Baby_Shower_Price_Is_Right.pptx")
  .then(() => console.log("Price Is Right presentation created!"))
  .catch(err => console.error(err));
