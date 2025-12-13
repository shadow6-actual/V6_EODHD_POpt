const pptxgen = require("pptxgenjs");
const fs = require("fs");

// Create presentation
const pptx = new pptxgen();
pptx.layout = "LAYOUT_16x9";

// Define colors (from theme)
const colors = {
  primary: "5EA8A7",
  primaryLight: "8CC4C3",
  secondary: "FF6B9D",
  surface: "FAF7F2",
  surfaceFg: "2C3E50",
  muted: "E8F4F3",
  mutedFg: "5D6D7E",
  accent: "FFF5E6",
  white: "FFFFFF",
  dark: "2C3E50"
};

// Jeopardy data structure
const categories = [
  {
    name: "SOUND MACHINES",
    questions: [
      {
        points: 100,
        clue:
          'This brand\'s "Rest" machine combines a night light, sound machine, and time-to-rise alarm clock, and it\'s app-controlled via Wi-Fi.',
        answer: "What is Hatch?",
        link: "https://www.amazon.com/Hatch-Baby-Machine-Trainer-Soother/dp/B08QVG9759"
      },
      {
        points: 200,
        clue:
          "This portable sound machine clips onto strollers, has multiple soothing sounds, and was designed as Hatch’s go-anywhere white noise solution.",
        answer: "What is the Hatch Go?",
        link: "https://www.amazon.com/Hatch-Portable-Baby-Soothing-Registry/dp/B0C5S8VB2K"
      },
      {
        points: 300,
        clue:
          "This cute plush bear responds to baby's cries and plays white noise for 30 or 60 minutes, designed by Dr. Harvey Karp.",
        answer: "What is the SNOObear?",
        link: "https://www.amazon.com/SNOObear-White-Noise-Machine-Cry-Activated/dp/B08KTK6MW6"
      },
      {
        points: 400,
        clue:
          "This 3-in-1 device from Happiest Baby serves as a white noise machine, customizable nightlight, and toddler sleep trainer.",
        answer: "What is the SNOObie?",
        link: "https://www.amazon.com/Happiest-Baby-SNOObie-Smart-Machine/dp/B0DL897TFS"
      },
      {
        points: 500,
        clue:
          "This smart bassinet automatically rocks and plays white noise, responding to baby's cries with four levels of soothing motion.",
        answer: "What is the SNOO?",
        link: "https://www.amazon.com/SNOO-Smart-Sleeper-Happiest-Baby/dp/B0716KN18Z"
      }
    ]
  },
  {
    name: "BABY CARRIERS",
    questions: [
      {
        points: 100,
        clue:
          'This brand makes the "Omni Classic" carrier that supports babies from 7–45 pounds in multiple positions.',
        answer: "What is Ergobaby?",
        link: "https://www.amazon.com/Ergobaby-Ergonomic-Carrier-Positions-Midnight/dp/B07B41952V"
      },
      {
        points: 200,
        clue:
          "This type of baby-wearing product wraps around the parent's body and is ideal for newborns from day one.",
        answer: "What is a baby wrap (or wrap carrier)?",
        link: "https://www.amazon.com/Ergobaby-Ergonomic-Carrier-Positions-Midnight/dp/B07B41952V"
      },
      {
        points: 300,
        clue:
          "This Ergobaby feature ensures baby sits in a natural, hip-healthy position with knees above bottom.",
        answer: "What is ergonomic design (or the M-position)?",
        link: "https://www.amazon.com/Ergobaby-Ergonomic-Carrier-Positions-Midnight/dp/B07B41952V"
      },
      {
        points: 400,
        clue:
          "This carrier accessory provides extra back support for parents during extended wearing sessions.",
        answer: "What is lumbar support?",
        link: "https://www.amazon.com/Ergobaby-Ergonomic-Carrier-Positions-Midnight/dp/B07B41952V"
      },
      {
        points: 500,
        clue:
          "Ergobaby carriers are certified by this organization that verifies products meet strict safety standards.",
        answer: "What is JPMA (Juvenile Products Manufacturers Association)?",
        link: "https://www.amazon.com/Ergobaby-Ergonomic-Carrier-Positions-Midnight/dp/B07B41952V"
      }
    ]
  },
  {
    name: "CAR SEATS",
    questions: [
      {
        points: 100,
        clue:
          'This popular brand makes the "SnugRide 35 Lite LX" infant car seat known for its affordable price.',
        answer: "What is Graco?",
        link: "https://www.amazon.com/Graco-SnugRide-SnugLock-Infant-adjustable/dp/B01MTM3I9M"
      },
      {
        points: 200,
        clue:
          'This premium brand makes the "MESA" infant car seat and the "VISTA" stroller system.',
        answer: "What is UPPAbaby?",
        link: "https://www.amazon.com/UPPAbaby-Installation-Innovative-SmartSecure-Technology/dp/B0DMTLT7RD"
      },
      {
        points: 300,
        clue:
          'This Italian brand makes the "KeyFit 35," known for being one of the easiest seats to install.',
        answer: "What is Chicco?",
        link: "https://www.amazon.com/Chicco-Rear-Facing-Infants-Compatible-Strollers/dp/B089HG2QTT"
      },
      {
        points: 400,
        clue:
          "The UPPAbaby Aria car seat weighs only this many pounds, making it one of the lightest carriers on the market.",
        answer: "What is 6.5 pounds?",
        link: "https://www.amazon.com/UPPAbaby-Lightweight-Portability-Included-Attachment/dp/B0CVBNKXZS"
      },
      {
        points: 500,
        clue:
          "This Lower Anchor and Tether system allows car seats to be installed without using the vehicle's seat belt.",
        answer: "What is LATCH?",
        link: "https://www.amazon.com/Chicco-Rear-Facing-Infants-Compatible-Strollers/dp/B089HG2QTT"
      }
    ]
  },
  {
    name: "FEEDING ESSENTIALS",
    questions: [
      {
        points: 100,
        clue:
          "This brand makes anti-colic bottles with distinctive blue vent inserts to reduce gas.",
        answer: "What is Dr. Brown's?",
        link: "https://www.amazon.com/Dr-Browns-Options-Bottle-4-Pack/dp/B01845QH7M"
      },
      {
        points: 200,
        clue:
          'This device heats bottles quickly and is available in "fast" and premium versions from Philips Avent.',
        answer: "What is a bottle warmer?",
        link: "https://www.amazon.com/Philips-Temperature-Control-Automatic-Shut-Off/dp/B0876T9DQZ"
      },
      {
        points: 300,
        clue:
          "This countertop machine sanitizes and dries bottles, pacifiers, and pump parts with hot steam and warm air.",
        answer: "What is a sterilizer (or sterilizer and dryer)?",
        link: "https://www.amazon.com/Sterilizer-HIYAKOI-Electric-Bottles-Essentials/dp/B0D474DSB6"
      },
      {
        points: 400,
        clue:
          "This automatic machine from Baby Brezza dispenses formula at the touch of a button.",
        answer: "What is a formula dispenser (or the Formula Pro)?",
        link: "https://www.amazon.com/Baby-Brezza-Formula-Pro-Advanced-Formula-Dispenser-White/dp/B07MYW28QR"
      },
      {
        points: 500,
        clue:
          "This Hatch product is a smart changing pad with a built-in wireless scale that tracks baby's weight gain through an app.",
        answer: "What is the Hatch Grow?",
        link: "https://www.amazon.com/Hatch-Baby-Changing-Scale-Limited/dp/B07L3B38N2"
      }
    ]
  },
  {
    name: "NURSERY GEAR",
    questions: [
      {
        points: 100,
        clue:
          'This foam changing pad is waterproof and often called a "Peanut" due to its shape.',
        answer: "What is the Keekaroo Peanut Changer?",
        link: "https://www.amazon.com/Keekaroo-0130009KR-0001-Peanut-Changer-Vanilla/dp/B00KSW970Y"
      },
      {
        points: 200,
        clue:
          "This portable item from Gathre is perfect for on-the-go diaper changes when away from home.",
        answer: "What is a portable changing pad (or mat)?",
        link: "https://www.amazon.com/Changing-Foldable-Wipeable-Resistant-Portable/dp/B0C1TP5SZ6"
      },
      {
        points: 300,
        clue:
          "This organizing caddy holds diapers, wipes, and creams and can be carried from room to room.",
        answer: "What is a diaper caddy?",
        link: "https://www.amazon.com/Parker-Baby-Diaper-Caddy-Organizer/dp/B0BGMKLZVX"
      },
      {
        points: 400,
        clue:
          "This air-purifying appliance from Dyson combines a purifier with this function to add moisture to nursery air.",
        answer: "What is a humidifier?",
        link: "https://www.amazon.com/Dyson-PH03-Purifier-Humidify-Cool/dp/B0BRLBCT9G"
      },
      {
        points: 500,
        clue:
          'This subscription-style brand from Lovevery delivers age-appropriate developmental toys often called "Play Kits."',
        answer: "What is Lovevery (or Lovevery Play Kits)?",
        link: "https://www.amazon.com/stores/LOVEVERY/page/2CD7D8E0-F2EE-451B-8A33-0D61AC3F707C"
      }
    ]
  }
];

// Slide 1: Title
let slide1 = pptx.addSlide();
slide1.background = { color: colors.primary };
slide1.addText("BABY SHOWER JEOPARDY", {
  x: 0.5,
  y: 1.5,
  w: 9,
  h: 1.5,
  fontSize: 54,
  fontFace: "Georgia",
  color: colors.white,
  bold: true,
  align: "center"
});
slide1.addText("Amazon Baby Registry Edition", {
  x: 0.5,
  y: 3.2,
  w: 9,
  h: 0.8,
  fontSize: 28,
  fontFace: "Arial",
  color: colors.accent,
  align: "center"
});
slide1.addText("Press → to begin", {
  x: 0.5,
  y: 4.5,
  w: 9,
  h: 0.5,
  fontSize: 16,
  fontFace: "Arial",
  color: colors.white,
  align: "center",
  italic: true
});

// Slide 2: Game Board Overview
let slide2 = pptx.addSlide();
slide2.background = { color: colors.surface };
slide2.addText("GAME BOARD", {
  x: 0.3,
  y: 0.2,
  w: 9.4,
  h: 0.6,
  fontSize: 32,
  fontFace: "Georgia",
  color: colors.primary,
  bold: true,
  align: "center"
});

// Create game board table
const boardData = [
  categories.map(c => ({
    text: c.name,
    options: {
      fill: colors.primary,
      color: colors.white,
      bold: true,
      fontSize: 11
    }
  })),
  ["$100", "$100", "$100", "$100", "$100"],
  ["$200", "$200", "$200", "$200", "$200"],
  ["$300", "$300", "$300", "$300", "$300"],
  ["$400", "$400", "$400", "$400", "$400"],
  ["$500", "$500", "$500", "$500", "$500"]
];

slide2.addTable(boardData, {
  x: 0.3,
  y: 1.0,
  w: 9.4,
  h: 3.8,
  colW: [1.88, 1.88, 1.88, 1.88, 1.88],
  border: { pt: 2, color: colors.dark },
  align: "center",
  valign: "middle",
  fontSize: 18,
  fontFace: "Arial",
  bold: true
});

slide2.addText(
  "Teams take turns selecting a category and point value. Answer in the form of a question!",
  {
    x: 0.5,
    y: 5.0,
    w: 9,
    h: 0.4,
    fontSize: 14,
    fontFace: "Arial",
    color: colors.mutedFg,
    align: "center",
    italic: true
  }
);

// Create question slides
for (let cat of categories) {
  for (let q of cat.questions) {
    // Clue slide
    let clueSlide = pptx.addSlide();
    clueSlide.background = { color: colors.surface };

    // Category header
    clueSlide.addShape(pptx.shapes.RECTANGLE, {
      x: 0,
      y: 0,
      w: 10,
      h: 0.8,
      fill: { color: colors.primary }
    });
    clueSlide.addText(cat.name, {
      x: 0.3,
      y: 0.1,
      w: 7,
      h: 0.6,
      fontSize: 24,
      fontFace: "Georgia",
      color: colors.white,
      bold: true
    });
    clueSlide.addText("$" + q.points, {
      x: 7.5,
      y: 0.1,
      w: 2.2,
      h: 0.6,
      fontSize: 28,
      fontFace: "Arial",
      color: colors.accent,
      bold: true,
      align: "right"
    });

    // Clue text
    clueSlide.addText("CLUE:", {
      x: 0.5,
      y: 1.2,
      w: 9,
      h: 0.4,
      fontSize: 16,
      fontFace: "Arial",
      color: colors.secondary,
      bold: true
    });
    clueSlide.addText(q.clue, {
      x: 0.5,
      y: 1.7,
      w: 9,
      h: 1.8,
      fontSize: 22,
      fontFace: "Georgia",
      color: colors.surfaceFg,
      valign: "top",
      wrap: true
    });

    // Answer section
    clueSlide.addShape(pptx.shapes.RECTANGLE, {
      x: 0.3,
      y: 3.8,
      w: 9.4,
      h: 1.6,
      fill: { color: colors.muted },
      line: { color: colors.primary, width: 2 }
    });
    clueSlide.addText("ANSWER:", {
      x: 0.5,
      y: 3.9,
      w: 9,
      h: 0.4,
      fontSize: 14,
      fontFace: "Arial",
      color: colors.secondary,
      bold: true
    });
    clueSlide.addText(q.answer, {
      x: 0.5,
      y: 4.3,
      w: 9,
      h: 0.6,
      fontSize: 24,
      fontFace: "Georgia",
      color: colors.primary,
      bold: true
    });
    clueSlide.addText(q.link, {
      x: 0.5,
      y: 4.9,
      w: 9,
      h: 0.4,
      fontSize: 10,
      fontFace: "Arial",
      color: colors.mutedFg,
      hyperlink: { url: q.link }
    });

    // OPTIONAL: If you download product photos, you can add them like this:
    // clueSlide.addImage({
    //   path: "images/example.jpg", // update per product
    //   x: 0.7,
    //   y: 2.0,
    //   w: 3.0,
    //   h: 2.2
    // });
  }
}

// Final slide
let finalSlide = pptx.addSlide();
finalSlide.background = { color: colors.primary };
finalSlide.addText("FINAL SCORES", {
  x: 0.5,
  y: 1.0,
  w: 9,
  h: 1,
  fontSize: 48,
  fontFace: "Georgia",
  color: colors.white,
  bold: true,
  align: "center"
});
finalSlide.addText("Team 1: _____________", {
  x: 1,
  y: 2.8,
  w: 8,
  h: 0.6,
  fontSize: 28,
  fontFace: "Arial",
  color: colors.accent,
  align: "center"
});
finalSlide.addText("Team 2: _____________", {
  x: 1,
  y: 3.6,
  w: 8,
  h: 0.6,
  fontSize: 28,
  fontFace: "Arial",
  color: colors.accent,
  align: "center"
});
finalSlide.addText("Congratulations to the winners!", {
  x: 0.5,
  y: 4.8,
  w: 9,
  h: 0.5,
  fontSize: 20,
  fontFace: "Georgia",
  color: colors.white,
  align: "center",
  italic: true
});

// Save presentation (relative to where you run the script)
pptx
  .writeFile("Baby_Shower_Jeopardy.pptx")
  .then(() => console.log("Presentation created successfully!"))
  .catch(err => console.error("Error:", err));
